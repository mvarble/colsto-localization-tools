# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "scipy", "polars"]
# ///
"""
Synthetic "where was this recorded?" dataset, shaped like the problem in the video.

Produces (in --out, default ./data):
  recording.wav       8 kHz mono, ~23 min. Two faint prop-plane flyovers ~920 s apart,
                      buried under wind rumble, mains hum, white noise and bird chirps.
  flights.parquet     One row per flight, FR24-ish *nested* schema:
                      flight_trail_list = list[struct{timestamp, lat, lon, alt_ft, gs_kt, track_deg, vs_fpm}]
                      Deliberately messy: null type codes, duplicate trail points, null altitudes.
  aircraft_types.csv  Type-code -> engine type lookup (like ICAO Doc 8643), with gaps.
  TRUTH.json          The answer. Don't open it until you've tried.

Physics: the audio is rendered with the *retarded-time* model. For each observer
sample time t_obs we solve  t_obs = t_e + |r(t_e) - obs| / c  for the emission time t_e,
then the waveform is the engine's phase evaluated at t_e. Doppler falls out exactly;
nothing is approximated with f0*c/(c - v_r).

Ground is flat at GROUND_M metres above sea level everywhere (stand-in for a DEM);
alt_ft in the tracks is above *sea level*, as with real ADS-B barometric altitude.

Run:  uv run tutorials/make_dataset.py --out data
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import polars as pl
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

C = 343.0          # speed of sound, m/s
FS = 8000          # audio sample rate
GROUND_M = 350.0   # flat ground elevation (MSL), metres
FT = 0.3048
KT = 0.514444


# ---------------------------------------------------------------- geometry helpers
class ENU:
    """Tiny equirectangular local frame. Fine for a 60 km box."""

    def __init__(self, lat0: float, lon0: float):
        self.lat0, self.lon0 = lat0, lon0
        self.k_lat = 111_320.0
        self.k_lon = 111_320.0 * math.cos(math.radians(lat0))

    def to_ll(self, x, y):
        return self.lat0 + np.asarray(y) / self.k_lat, self.lon0 + np.asarray(x) / self.k_lon


def integrate_path(t, speed, heading_deg, p0=(0.0, 0.0)):
    """Integrate speed(t) [m/s] and heading(t) [deg, 0=N, 90=E] into x(east), y(north)."""
    dt = np.gradient(t)
    h = np.radians(heading_deg)
    vx, vy = speed * np.sin(h), speed * np.cos(h)
    x = p0[0] + np.cumsum(vx * dt) - vx[0] * dt[0]
    y = p0[1] + np.cumsum(vy * dt) - vy[0] * dt[0]
    return x, y


def adsb_reports(fid, t, x, y, alt_m, enu, rng, period=1.0, jitter=0.0):
    """Down-sample a fine truth trajectory into ADS-B-ish 1 Hz reports."""
    tr = np.arange(t[0], t[-1], period)
    if jitter:
        tr = np.sort(tr + rng.uniform(-jitter, jitter, tr.size))
    xr, yr, ar = (np.interp(tr, t, v) for v in (x, y, alt_m))
    vx, vy, vz = (np.gradient(v, tr) for v in (xr, yr, ar))
    lat, lon = enu.to_ll(xr, yr)
    return {
        "timestamp": np.round(tr).astype(np.int64),
        "lat": np.round(lat, 5),
        "lon": np.round(lon, 5),
        "alt_ft": (np.round(ar / FT / 25) * 25).astype(np.int64),   # 25 ft quantisation
        "gs_kt": np.round(np.hypot(vx, vy) / KT, 1),
        "track_deg": np.round(np.degrees(np.arctan2(vx, vy)) % 360, 1),
        "vs_fpm": (np.round(vz / FT * 60 / 64) * 64).astype(np.int64),
    }


# ---------------------------------------------------------------- scene
def build_scene(rng, t_rec):
    """Return (observer, heard flights with fine trajectories, decoy flights)."""
    enu = ENU(44.06, -121.31)            # box centre (somewhere in central Oregon)
    obs = np.array([rng.uniform(-9e3, 9e3), rng.uniform(-9e3, 9e3), GROUND_M + 2.0])
    airport = np.array([obs[0] + 14e3 * rng.choice([-1, 1]), obs[1] - 11e3])

    heard = []
    # event 1: C172, speeding up a little on approach and a gentle turn after CPA -> non-ideal curve
    tt = np.arange(-700, 700, 0.05)
    spd = 51 + 6 / (1 + np.exp(-(tt + 60) / 25))            # 51 -> 57 m/s around t=-60
    hdg = 72 + 9 / (1 + np.exp(-(tt - 40) / 30))            # 72 -> 81 deg after CPA
    heard.append(dict(type_code="C172", callsign="N738XQ", f0=96.0, harmonics=[1, .55, .3, .15],
                      t=tt, speed=spd, heading=hdg, alt_m=GROUND_M + 1250.0, offset=1350.0,
                      want_delayed_cpa=t_rec + 231.0, level=0.015))
    # event 2: King Air, faster, higher, straight
    tt = np.arange(-500, 500, 0.05)
    heard.append(dict(type_code="BE20", callsign="N92KA", f0=138.0, harmonics=[1, .7, .45, .2, .1],
                      t=tt, speed=np.full_like(tt, 118.0), heading=np.full_like(tt, 203.0),
                      alt_m=GROUND_M + 2600.0, offset=2300.0,
                      want_delayed_cpa=t_rec + 231.0 + 920.0, level=0.018))

    for f in heard:
        x, y = integrate_path(f["t"], f["speed"], f["heading"])
        i0 = int(np.argmin(abs(f["t"])))
        x, y = x - x[i0], y - y[i0]                          # path passes through origin at t=0
        # put the observer off to the right of the t=0 point by `offset`
        h0 = math.radians(f["heading"][i0])
        right = np.array([math.cos(h0), -math.sin(h0)])
        x = x + obs[0] - right[0] * f["offset"]
        y = y + obs[1] - right[1] * f["offset"]
        z = np.full_like(x, f["alt_m"])
        r = np.sqrt((x - obs[0]) ** 2 + (y - obs[1]) ** 2 + (z - obs[2]) ** 2)
        i = int(np.argmin(r))
        delayed = f["t"][i] + r[i] / C
        f["t"] = f["t"] + (f["want_delayed_cpa"] - delayed)   # shift to wall-clock epoch
        f.update(x=x, y=y, z=z, cpa_slant_m=float(r[i]), cpa_epoch=float(f["t"][i]),
                 delayed_cpa_epoch=float(f["t"][i] + r[i] / C), cpa_speed_ms=float(f["speed"][i]))

    # decoys: random overflights + airport traffic. During the recording none come within 15 km
    pistons = ["C172", "PA28", "SR22", "BE36"]
    turboprops = ["BE20", "C208", "DH8D", "AT76", "PC12"]
    jets = ["B738", "A320", "E75L", "CRJ9", "B77W", "A21N", "GLF4", "C56X"]
    decoys = []
    t_lo, t_hi = t_rec - 4 * 3600, t_rec + 4 * 3600
    while len(decoys) < 260:
        kind = rng.choice(["jet", "piston", "turboprop"], p=[0.3, 0.4, 0.3])
        is_jet = kind == "jet"
        tc = rng.choice({"jet": jets, "piston": pistons, "turboprop": turboprops}[kind])
        at_airport = (not is_jet) and rng.random() < 0.75       # busy GA airport nearby
        spd = {"jet": rng.uniform(200, 250), "piston": rng.uniform(48, 68), "turboprop": rng.uniform(95, 135)}[kind]
        hdg = rng.uniform(0, 360)
        dur = 800.0 if at_airport else 1500.0
        t = np.arange(0, dur, 0.5)
        if at_airport:              # depart or arrive at the airport, climbing/descending
            x, y = integrate_path(t, np.full_like(t, spd), np.full_like(t, hdg), tuple(airport))
            alt = GROUND_M + np.minimum(3000.0, 4.0 * t)
            if rng.random() < 0.5:   # arrival = reversed departure
                x, y, alt = x[::-1], y[::-1], alt[::-1]
        else:
            # line passing somewhere through the box
            c0 = rng.uniform(-28e3, 28e3, 2)
            x, y = integrate_path(t - dur / 2, np.full_like(t, spd), np.full_like(t, hdg), (0, 0))
            x, y = x - x[t.size // 2] + c0[0], y - y[t.size // 2] + c0[1]
            alt = np.full_like(t, rng.uniform(9000, 11500) if is_jet else GROUND_M + rng.uniform(700, 3200))
        t0 = rng.uniform(t_lo, t_hi)
        tt = t + t0
        during = (tt > t_rec - 120) & (tt < t_rec + 1500)
        if during.any() and np.hypot(x[during] - obs[0], y[during] - obs[1]).min() < 15e3:
            continue
        decoys.append(dict(type_code=str(tc), callsign=f"{'AAL' if is_jet else 'N'}{rng.integers(100, 9999)}",
                           t=tt, x=x, y=y, z=alt, airport=at_airport))
    return enu, obs, airport, heard, decoys


# ---------------------------------------------------------------- audio
def render_flyover(f, obs, t_audio_epoch, rng):
    """Exact retarded-time rendering of one aircraft's harmonic engine tone."""
    out = np.zeros(t_audio_epoch.size)
    # engine fundamental wanders slightly (rpm hunting): integrate phase on the fine grid
    tf = f["t"]
    f0_t = f["f0"] * (1 + 0.004 * np.sin(2 * np.pi * tf / 37.0) + 0.002 * np.sin(2 * np.pi * tf / 11.3))
    phase = 2 * np.pi * np.concatenate([[0], np.cumsum(0.5 * (f0_t[1:] + f0_t[:-1]) * np.diff(tf))])

    def rng_at(te):
        x = np.interp(te, tf, f["x"]) - obs[0]
        y = np.interp(te, tf, f["y"]) - obs[1]
        z = np.interp(te, tf, f["z"]) - obs[2]
        return np.sqrt(x * x + y * y + z * z)

    # only bother where the aircraft is within ~14 km
    mask = (t_audio_epoch > tf[0] + 60) & (t_audio_epoch < tf[-1])
    to = t_audio_epoch[mask]
    te = to - rng_at(to) / C
    for _ in range(6):                        # fixed-point iteration converges fast (|v|/c < 1)
        te = to - rng_at(te) / C
    R = rng_at(te)
    amp = f["level"] * (1000.0 / R) * np.exp(-R / 9000.0)        # spherical spreading + crude absorption
    ph = np.interp(te, tf, phase)
    sig = np.zeros(to.size)
    for k, a in enumerate(f["harmonics"], start=1):
        sig += a * np.sin(k * ph + rng.uniform(0, 2 * np.pi))
    edge = np.clip((to - to[0]) / 30, 0, 1) * np.clip((to[-1] - to) / 30, 0, 1)
    out[mask] = amp * sig * edge
    return out


def background(n, rng):
    t = np.arange(n) / FS
    white = rng.normal(0, 0.0045, n)
    rumble = sosfilt(butter(2, 120, "low", fs=FS, output="sos"), rng.normal(0, 0.12, n))
    # slow wind gusts: a smooth envelope (~5 s correlation) between ~0.4x and ~1.6x
    g = np.convolve(rng.normal(0, 1, n // FS + 20), np.hanning(9), "same")
    gust = np.interp(np.arange(n) / FS, np.arange(g.size), 1 + 0.6 * np.tanh(g / g.std()))
    hum = 0.0025 * (np.sin(2 * np.pi * 60 * t) + 0.5 * np.sin(2 * np.pi * 120 * t + 1) + 0.3 * np.sin(2 * np.pi * 180 * t))
    x = white + rumble * gust + hum
    for _ in range(140):                                          # bird chirps 2-4 kHz
        s = rng.integers(0, n - FS)
        L = int(rng.uniform(0.08, 0.35) * FS)
        tt = np.arange(L) / FS
        f = rng.uniform(2000, 3800) + rng.uniform(-1500, 1500) * tt / tt[-1]
        x[s:s + L] += rng.uniform(0.005, 0.04) * np.sin(2 * np.pi * np.cumsum(f) / FS) * np.hanning(L)
    return x


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data")
    ap.add_argument("--seed", type=int, default=8)
    ap.add_argument("--duration", type=float, default=1400.0)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    t_rec = 1788907000.0 + rng.uniform(0, 6000)          # recording start, epoch s (the unknown!)
    enu, obs, airport, heard, decoys = build_scene(rng, t_rec)

    # ---- audio
    n = int(a.duration * FS)
    t_epoch = t_rec + np.arange(n) / FS
    audio = background(n, rng)
    for f in heard:
        audio += render_flyover(f, obs, t_epoch, rng)
    audio = audio / np.abs(audio).max() * 0.9
    wavfile.write(out / "recording.wav", FS, (audio * 32767).astype(np.int16))

    # ---- flight table (nested, messy)
    rows = []
    fid = 1_099_966_000
    all_flights = [dict(f, heard=True) for f in heard] + [dict(f, heard=False) for f in decoys]
    order = rng.permutation(len(all_flights))
    truth_ids = {}
    for j in order:
        f = all_flights[j]
        fid += int(rng.integers(1, 400))
        alt_m = f["z"] if np.ndim(f["z"]) else np.full_like(f["x"], f["z"])
        rep = adsb_reports(fid, f["t"], f["x"], f["y"], alt_m, enu, rng,
                           period=1.0 if f["heard"] else float(rng.choice([1.0, 1.0, 2.0, 5.0])),
                           jitter=0.0 if f["heard"] else 0.3)
        trail = [dict(zip(rep, vals)) for vals in zip(*rep.values())]
        if not f["heard"] and rng.random() < 0.15:           # duplicate reports
            dup = rng.choice(len(trail), size=max(1, len(trail) // 50), replace=False)
            trail = sorted(trail + [dict(trail[d]) for d in dup], key=lambda r: r["timestamp"])
        for r in trail:
            r["alt_ft"] = int(r["alt_ft"])
            if rng.random() < 0.003:
                r["alt_ft"] = None                              # dropouts
        tc = f["type_code"]
        if not f["heard"] and rng.random() < 0.07:
            tc = None                                           # unknown type
        rows.append(dict(flightid=fid, callsign=f["callsign"], type_code=tc,
                         first_seen_utc=str(np.datetime64(int(trail[0]["timestamp"]), "s")) + "Z",
                         flight_trail_list=trail))
        if f["heard"]:
            truth_ids[f["callsign"]] = fid

    df = pl.DataFrame(rows)
    df.write_parquet(out / "flights.parquet")

    # ---- type lookup: like ICAO Doc 8643, but with some types missing
    lut = {"C172": "Piston", "PA28": "Piston", "SR22": "Piston", "BE36": "Piston",
           "BE20": "Turboprop/Turboshaft", "C208": "Turboprop/Turboshaft", "DH8D": "Turboprop/Turboshaft",
           "AT76": "Turboprop/Turboshaft",            # PC12 deliberately missing
           "B738": "Jet", "A320": "Jet", "E75L": "Jet", "CRJ9": "Jet", "B77W": "Jet", "A21N": "Jet",
           "GLF4": "Jet"}                             # C56X deliberately missing
    pl.DataFrame({"type_designator": list(lut), "engine_type": list(lut.values())}).write_csv(out / "aircraft_types.csv")

    # ---- truth
    lat, lon = enu.to_ll(obs[0], obs[1])
    alat, alon = enu.to_ll(airport[0], airport[1])
    truth = dict(
        observer_lat=float(lat), observer_lon=float(lon), ground_elev_m=GROUND_M,
        recording_start_epoch=t_rec, airport_lat=float(alat), airport_lon=float(alon),
        events=[dict(callsign=f["callsign"], flightid=truth_ids[f["callsign"]], type_code=f["type_code"],
                     f0_hz=f["f0"], cpa_slant_m=round(f["cpa_slant_m"], 1),
                     cpa_speed_ms=round(f["cpa_speed_ms"], 2),
                     delayed_cpa_epoch=round(f["delayed_cpa_epoch"], 2),
                     delayed_cpa_audio_s=round(f["delayed_cpa_epoch"] - t_rec, 2)) for f in heard],
    )
    (out / "TRUTH.json").write_text(json.dumps(truth, indent=2))
    print(f"wrote {out}/recording.wav ({a.duration:.0f}s @ {FS} Hz), flights.parquet ({len(df)} flights), "
          f"aircraft_types.csv, TRUTH.json")


if __name__ == "__main__":
    main()
