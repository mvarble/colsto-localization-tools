# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "scipy", "polars"]
# ///
"""
Fit the straight-line, retarded-time Doppler model to hand-traced points and report *ranges*,
which is what the funnel filters need (the video: "I can't say it was going exactly 100, but it wasn't 70").

Input: CSV with columns  t_s,f_hz   (from doppler_explorer.py "Copy trace CSV", a Sonic Visualiser
Time Values layer export, or Audacity labels). If you traced the k-th harmonic, pass --harmonic k.

    uv run tutorials/fit_trace.py trace.csv --harmonic 3
    uv run tutorials/fit_trace.py --demo            # synthesises a noisy trace and fits it
"""
import argparse
import sys

import numpy as np
import polars as pl
from scipy.optimize import brentq, least_squares

C = 343.0


def model(t, f0, v, d, t0):
    """Heard frequency at observer times t. Solve te + R(te)/c = t for each t (monotone in te)."""
    te_c = t0 - d / C
    out = np.empty_like(t, dtype=float)
    for i, ti in enumerate(t):
        g = lambda te: te + np.hypot(v * (te - te_c), d) / C - ti
        te = brentq(g, ti - 1e5 / C, ti + 1)            # heard time is always after emission
        x = v * (te - te_c)
        out[i] = f0 * C / (C + v * x / np.hypot(x, d))
    return out


def fit(t, f, guess):
    res = least_squares(lambda p: model(t, *p) - f, guess, x_scale=[10, 10, 500, 5],
                        bounds=([1, 1, 50, t.min() - 300], [5000, 340, 50000, t.max() + 300]))
    J = res.jac
    dof = max(1, t.size - 4)
    s2 = (res.fun ** 2).sum() / dof
    try:
        cov = np.linalg.inv(J.T @ J) * s2
        sig = np.sqrt(np.diag(cov))
    except np.linalg.LinAlgError:
        sig = np.full(4, np.nan)
    return res.x, sig, np.sqrt(s2)


ap = argparse.ArgumentParser()
ap.add_argument("csv", nargs="?")
ap.add_argument("--harmonic", type=int, default=1)
ap.add_argument("--demo", action="store_true")
a = ap.parse_args()

if a.demo:
    rng = np.random.default_rng(1)
    t = np.sort(rng.uniform(150, 310, 40))
    truth = (96.0, 56.5, 1838.0, 231.0)
    f = 3 * model(t, *truth) + rng.normal(0, 1.0, t.size)      # traced 3rd harmonic, ~1 Hz click error
    a.harmonic = 3
    print("truth  f0=%.1f v=%.1f d=%.0f t0=%.1f" % truth)
elif a.csv:
    # Accept `t_s,f_hz` with header, or headerless exports (Sonic Visualiser Time Values: time,value[,label]),
    # comma- or tab-separated: first two numeric columns are time and frequency.
    first = open(a.csv).readline()
    sep = "\t" if "\t" in first else ","
    try:
        float(first.split(sep)[0])
        header = False
    except ValueError:
        header = True
    df = pl.read_csv(a.csv, separator=sep, has_header=header)
    if header and {"t_s", "f_hz"} <= set(df.columns):
        t, f = df["t_s"].to_numpy(), df["f_hz"].to_numpy()
    else:
        t, f = df[:, 0].cast(pl.Float64).to_numpy(), df[:, 1].cast(pl.Float64).to_numpy()
else:
    sys.exit(__doc__)

f = f / a.harmonic
# crude initial guess straight from the data: plateaus -> f0 & v, steepest point -> t0
fhi, flo = np.percentile(f, 95), np.percentile(f, 5)
f0g = 2 * fhi * flo / (fhi + flo)
vg = C * (fhi - flo) / (fhi + flo)
slope = np.gradient(f, t)
t0g = t[np.argmin(slope)]
dg = max(200.0, f0g * vg ** 2 / (C * max(1e-3, -slope.min())))
p, sig, rms = fit(t, f, [f0g, vg, dg, t0g])
names = ["f0 (Hz)", "v (m/s)", "d (m)", "t0 (s)"]
print(f"fit on {t.size} points, residual rms {rms:.2f} Hz (fundamental)")
for n, v, s in zip(names, p, sig):
    print(f"  {n:8s} {v:9.2f}  +/- {s:.2f}   -> filter range [{v - 3 * s:.1f}, {v + 3 * s:.1f}]  (3 sigma)")
print("Note: d and v trade off against each other; widen ranges if the curve is asymmetric "
      "(speed/heading changes), as the video did.")
