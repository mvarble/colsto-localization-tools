# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "scipy", "polars", "pyarrow", "plotly", "geopandas", "pyogrio", "shapely"]
# ///
"""
Final stage of the video's pipeline (17:00-22:40): for each surviving candidate, model the exact
Doppler curve the candidate *would* have heard from the real (ADS-B) flight geometry, lay it on the
spectrogram and score it by the brightness it covers.

  * event 1 placement: sweep a few seconds of time offset and a few % of f0 (measurement error)
  * event 2 placement: *locked* to event 1 by flight geometry -- only f0 is swept
  * refine: re-score the best flight pairs on a 50 m grid -> heat map layer for QGIS

    uv run tutorials/polars_funnel.py data        # produces data/funnel/stage2_speed_dist.csv
    uv run tutorials/score_candidates.py data     # -> data/funnel/scores.parquet, compare.html, fine.gpkg
    uv run tutorials/quick_scatter.py data/funnel/scores.parquet --x score1 --y score2 --group pair --score total

Measured-from-audio inputs (use doppler_explorer.py to get your own): --a1, --f1, --f2.
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).parent))
from htmlkit import load_wav, pack_u8, spec_db, write_page  # noqa: E402

C = 343.0
GROUND_M = 350.0

ap = argparse.ArgumentParser()
ap.add_argument("data", nargs="?", default="data")
ap.add_argument("--a1", type=float, default=231.0, help="audio time (s) of event-1 delayed CPA, measured")
ap.add_argument("--offset", type=float, default=920.0, help="measured audio offset event2 - event1")
ap.add_argument("--f1", type=float, default=96.0, help="event-1 fundamental, measured")
ap.add_argument("--f2", type=float, default=138.0, help="event-2 fundamental, measured")
ap.add_argument("--harmonics", type=int, default=4)
ap.add_argument("--plotly", default="cdn", choices=["cdn", "inline"])
a = ap.parse_args()
D = Path(a.data)
OUT = D / "funnel"

# ---------------------------------------------------------------- inputs
cand = pl.read_csv(OUT / "stage2_speed_dist.csv")
cand = cand.with_columns(pair=pl.concat_str("flightid", pl.lit("-"), "flightid_2"))
flights = pl.read_parquet(D / "flights.parquet")
pts = (flights.select("flightid", "flight_trail_list").explode("flight_trail_list").unnest("flight_trail_list")
       .unique(["flightid", "timestamp"]).drop_nulls("alt_ft").sort("flightid", "timestamp"))
# same local frame as polars_funnel.py
LAT0, LON0 = pts["lat"].mean(), pts["lon"].mean()
KX, KY = 111_320.0 * math.cos(math.radians(LAT0)), 111_320.0
pts = pts.with_columns(x=(pl.col("lon") - LON0) * KX, y=(pl.col("lat") - LAT0) * KY, z=pl.col("alt_ft") * 0.3048)
tracks = {fid: g for (fid,), g in pts.group_by(["flightid"])}

fs, audio = load_wav(D / "recording.wav")
W = 90.0
specs = {}
for ev, ac in [(1, a.a1), (2, a.a1 + a.offset)]:
    t, f, Z = spec_db(audio, fs, ac - W, ac + W, 40, 800, nperseg=4096, whiten=True)
    specs[ev] = (t, f, np.clip(Z, -3, 6))                     # clip so one loud bird can't dominate


def model_curve(fid, ox, oy, step=0.5):
    """Heard time (epoch) and Doppler factor c/(c+v_away) at observer (ox, oy), retarded time."""
    g = tracks[fid]
    ts = g["timestamp"].to_numpy().astype(float)
    te = np.arange(ts[0], ts[-1], step)
    x, y, z = (np.interp(te, ts, g[c].to_numpy()) for c in ("x", "y", "z"))
    R = np.sqrt((x - ox) ** 2 + (y - oy) ** 2 + (z - GROUND_M) ** 2)
    t_obs = te + R / C
    v_away = np.gradient(R, te)
    i = int(np.argmin(R))
    return t_obs - t_obs[i], C / (C + v_away), t_obs[i]   # time relative to delayed CPA


def score(ev, trel, fac, t_anchor, f0s, dts):
    """Mean whitened brightness under the curve for every (dt, f0) combo. Returns (len(dts), len(f0s))."""
    t, f, Z = specs[ev]
    keep = np.abs(trel) < W - 5
    trel, fac = trel[keep], fac[keep]
    ti = np.rint((t_anchor + trel[None, :] + dts[:, None] - t[0]) / (t[1] - t[0])).astype(int)   # (dt, n)
    ti = np.clip(ti, 0, t.size - 1)
    out = np.zeros((dts.size, f0s.size))
    cnt = np.zeros_like(out)
    df = f[1] - f[0]
    for k in range(1, a.harmonics + 1):
        fr = k * f0s[:, None] * fac[None, :]                                # (f0, n)
        fi = np.rint((fr - f[0]) / df).astype(int)
        ok = (fi >= 0) & (fi < f.size)                                       # (f0, n)
        fi = np.clip(fi, 0, f.size - 1)
        vals = Z[fi[None, :, :], ti[:, None, :]]                             # (dt, f0, n)
        out += (vals * ok[None]).sum(-1)
        cnt += ok.sum(-1)[None, :]
    return out / np.maximum(cnt, 1)


DTS = np.arange(-4, 4.01, 0.25)


def score_point(f1id, f2id, ox, oy):
    tr1, fac1, dcpa1 = model_curve(f1id, ox, oy)
    tr2, fac2, dcpa2 = model_curve(f2id, ox, oy)
    f0s1 = a.f1 * np.linspace(0.97, 1.03, 25)
    s1 = score(1, tr1, fac1, a.a1, f0s1, DTS)
    i, j = np.unravel_index(np.argmax(s1), s1.shape)
    dt_best = DTS[i]
    # locked: event 2 lands where flight geometry says, relative to event 1's corrected placement
    anchor2 = a.a1 + dt_best + (dcpa2 - dcpa1)
    f0s2 = a.f2 * np.linspace(0.97, 1.03, 25)
    s2 = score(2, tr2, fac2, anchor2, f0s2, np.array([0.0]))
    k = int(np.argmax(s2[0]))
    return dict(score1=float(s1[i, j]), score2=float(s2[0, k]), dt_shift=float(dt_best), f0_1=float(f0s1[j]),
                f0_2=float(f0s2[k]), locked_offset=float(dcpa2 - dcpa1), anchor2=float(anchor2))


rows = []
for r in cand.iter_rows(named=True):
    rows.append(dict(r, **score_point(r["flightid"], r["flightid_2"], r["gx"], r["gy"])))
scores = (pl.DataFrame(rows)
          .with_columns(total=pl.col("score1") + pl.col("score2"),
                        lat=LAT0 + pl.col("gy") / KY, lon=LON0 + pl.col("gx") / KX)
          .sort("total", descending=True))
scores.write_parquet(OUT / "scores.parquet")
best = scores.group_by("pair").agg(pl.all().sort_by("total", descending=True).first()).sort("total", descending=True)
print(best.select("pair", "total", "score1", "score2", "locked_offset", "lat", "lon").head(8))

# ---------------------------------------------------------------- refine best pairs on a 50 m grid
fine = []
for r in best.head(3).iter_rows(named=True):
    for dx in np.arange(-800, 801, 50):
        for dy in np.arange(-800, 801, 50):
            s = score_point(r["flightid"], r["flightid_2"], r["gx"] + dx, r["gy"] + dy)
            fine.append(dict(pair=r["pair"], gx=r["gx"] + dx, gy=r["gy"] + dy, **s))
fine = (pl.DataFrame(fine).with_columns(total=pl.col("score1") + pl.col("score2"),
                                        lat=LAT0 + pl.col("gy") / KY, lon=LON0 + pl.col("gx") / KX))
top = fine.sort("total", descending=True).row(0, named=True)
print(f"best fine point: {top['lat']:.5f}, {top['lon']:.5f}  total={top['total']:.2f}  pair={top['pair']}")
import geopandas as gpd  # noqa: E402

pdf = fine.to_pandas()
gpkg = OUT / "fine.gpkg"
gpkg.unlink(missing_ok=True)
gpd.GeoDataFrame(pdf, geometry=gpd.points_from_xy(pdf.lon, pdf.lat), crs="EPSG:4326").to_file(gpkg, layer="fine_scores")
print("wrote", gpkg)

# ---------------------------------------------------------------- compare page: top-N curves over the spectrograms
N = 5
curves = []
for r in best.head(N).iter_rows(named=True):
    tr1, fac1, _ = model_curve(r["flightid"], r["gx"], r["gy"])
    tr2, fac2, _ = model_curve(r["flightid_2"], r["gx"], r["gy"])
    k1, k2 = np.abs(tr1) < W, np.abs(tr2) < W
    curves.append(dict(label=f"#{len(curves)+1} {r['pair']} total={r['total']:.2f}",
                       e1=dict(t=np.round(a.a1 + r["dt_shift"] + tr1[k1], 2).tolist(), fac=np.round(fac1[k1], 5).tolist(), f0=r["f0_1"]),
                       e2=dict(t=np.round(r["anchor2"] + tr2[k2], 2).tolist(), fac=np.round(fac2[k2], 5).tolist(), f0=r["f0_2"])))
data = dict(curves=curves, nh=a.harmonics,
            s1=dict(t=np.round(specs[1][0], 2).tolist(), f=np.round(specs[1][1], 1).tolist(), z=pack_u8(specs[1][2])),
            s2=dict(t=np.round(specs[2][0], 2).tolist(), f=np.round(specs[2][1], 1).tolist(), z=pack_u8(specs[2][2])))
body = """<div class="panel" id="boxes"></div><div id="p1" style="height:430px"></div><div id="p2" style="height:430px"></div>"""
js = r"""
const COLORS = ["#ff4d4d", "#4dff88", "#ffd24d", "#4dc3ff", "#ff4dff"];
const boxes = document.getElementById("boxes");
DATA.curves.forEach((c, i) => boxes.insertAdjacentHTML("beforeend",
  `<label style="color:${COLORS[i]}"><input type=checkbox data-i=${i} ${i < 2 ? "checked" : ""}> ${c.label}</label><br>`));
function traces(ev) {
  const s = DATA["s" + ev], out = [{type: "heatmap", x: s.t, y: s.f, z: unpackU8(s.z), colorscale: "Greys", reversescale: true, showscale: false}];
  DATA.curves.forEach((c, i) => {
    const e = c["e" + ev];
    for (let k = 1; k <= DATA.nh; k++)
      out.push({type: "scatter", mode: "lines", x: e.t, y: e.fac.map(v => k * e.f0 * v), meta: i,
                line: {color: COLORS[i], width: 1.5}, opacity: 0.8, name: c.label, showlegend: false, visible: i < 2});
  });
  return out;
}
const lay = t => ({title: {text: t}, paper_bgcolor: "#16181d", plot_bgcolor: "#16181d", font: {color: "#ccc"},
                   margin: {l: 50, r: 10, t: 30, b: 40}, xaxis: {title: {text: "recording time (s)"}}, yaxis: {title: {text: "Hz"}}});
Plotly.newPlot("p1", traces(1), lay("event 1 (free placement)"));
Plotly.newPlot("p2", traces(2), lay("event 2 (locked to event 1 by flight geometry)"));
boxes.addEventListener("input", () => {
  const on = [...boxes.querySelectorAll("input")].map(b => b.checked);
  for (const id of ["p1", "p2"]) {
    const gd = document.getElementById(id);
    const idx = gd.data.map((t, j) => j).filter(j => j > 0);
    Plotly.restyle(gd, {visible: idx.map(j => on[gd.data[j].meta])}, idx);
  }
});
"""
write_page(OUT / "compare.html", "Top candidates: modelled curves vs spectrogram", body, data, js, a.plotly)
print("wrote", OUT / "compare.html")
