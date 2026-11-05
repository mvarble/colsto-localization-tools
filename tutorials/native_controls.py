# /// script
# requires-python = ">=3.11"
# dependencies = ["polars", "pyarrow", "plotly"]
# ///
"""
Tier 1: Plotly's *built-in* controls, pure Python, zero JavaScript.
Re-creates the video's "CPA Timeline" (7:14) for one grid point.

    uv run tutorials/native_controls.py data            # picks the best-scoring point
    uv run tutorials/native_controls.py data --gid 12345

Built-in controls can only switch between *precomputed* states:
  * layout.sliders  -> each step calls restyle / relayout / update / animate with fixed args
  * layout.updatemenus -> buttons or dropdowns, same four methods
So: great for "sweep one discrete parameter" or "toggle these traces". For a continuous model
(f0, v, d, t0 all live), use the JS tier (doppler_explorer.py) or marimo.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path

import plotly.graph_objects as go
import polars as pl

ap = argparse.ArgumentParser()
ap.add_argument("data", nargs="?", default="data")
ap.add_argument("--gid", type=int)
ap.add_argument("--offset", type=float, default=920.0)
ap.add_argument("--out", default="cpa_timeline.html")
a = ap.parse_args()
F = Path(a.data) / "funnel"

hear = pl.read_parquet(F / "hearings.parquet")
types = pl.read_csv(Path(a.data) / "aircraft_types.csv")
gid = a.gid or pl.read_parquet(F / "scores.parquet").sort("total", descending=True)["gid"][0]
h = (hear.filter(pl.col("gid") == gid)
     .join(types, left_on="type_code", right_on="type_designator", how="left")
     .with_columns(t=pl.from_epoch((pl.col("t_dcpa") * 1000).cast(pl.Int64), time_unit="ms"),
                   jet=pl.col("engine_type") == "Jet")
     .sort("t_dcpa"))
print(f"grid point {gid}: {h.height} flights heard within range")

fig = go.Figure()
for is_jet, name, color in [(False, "props / unknown", "#4da3ff"), (True, "jets", "#ff7f50")]:
    d = h.filter(pl.col("jet").fill_null(False) == is_jet)
    fig.add_trace(go.Scatter(
        x=d["t"].to_list(), y=[1] * d.height, mode="markers", name=name,
        marker=dict(size=10, color=color, symbol="line-ns-open", line=dict(width=2)),
        customdata=d.select("flightid", "type_code", "r", "gs_ms").rows(),
        hovertemplate="flight %{customdata[0]} (%{customdata[1]})<br>slant %{customdata[2]:.0f} m"
                      "<br>gs %{customdata[3]:.0f} m/s<br>%{x}<extra></extra>"))

# One slider step per heard flight: move the [t, t + offset] window so its left edge sits on that flight.
# GOTCHA: give shapes the same *kind* of x value as the traces. Traces got naive UTC datetimes (-> ISO
# strings); epoch-ms numbers here would be interpreted in the *browser's* timezone and land hours off.
iso = lambda t: datetime.fromtimestamp(t, timezone.utc).replace(tzinfo=None).isoformat()
steps = []
for row in h.iter_rows(named=True):
    t0 = row["t_dcpa"]
    win = dict(type="rect", xref="x", yref="paper", x0=iso(t0), x1=iso(t0 + a.offset), y0=0, y1=1,
               fillcolor="rgba(255,255,255,0.08)", line=dict(color="#aaa", dash="dash"))
    steps.append(dict(method="relayout", label=str(row["flightid"])[-4:],
                      args=[{"shapes": [win], "title.text": f"window starts at flight {row['flightid']} "
                                                           f"({row['type_code']}, {row['r']:.0f} m)"}]))

fig.update_layout(
    template="plotly_dark", height=430, yaxis=dict(visible=False, range=[0.5, 1.5]),
    xaxis=dict(type="date", title="delayed-CPA time (UTC)"),
    title=f"CPA timeline at grid point {gid}  ({a.offset:.0f} s window)",
    sliders=[dict(active=0, steps=steps, pad=dict(t=60), currentvalue=dict(prefix="window anchored on flight ...")),],
    updatemenus=[dict(type="buttons", direction="right", x=0, y=1.25, font=dict(color="#111"), buttons=[
        dict(label="all", method="restyle", args=[{"visible": [True, True]}]),
        dict(label="props only", method="restyle", args=[{"visible": [True, False]}]),
        dict(label="jets only", method="restyle", args=[{"visible": [False, True]}]),
    ])],
)
if steps:
    fig.update_layout(shapes=steps[0]["args"][0]["shapes"])
fig.write_html(a.out, include_plotlyjs="cdn")
print("wrote", a.out)
