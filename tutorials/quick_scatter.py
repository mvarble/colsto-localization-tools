# /// script
# requires-python = ">=3.11"
# dependencies = ["polars", "pyarrow", "numpy", "scipy", "plotly"]
# ///
"""
Schema-agnostic scatter explorer: point it at ANY parquet/csv and get one HTML page with
  * x / y / colour dropdowns over every numeric column
  * "colour by group" + "only best row per group" checkboxes  (the video's 21:31 page)
  * a range slider to threshold any numeric column
  * hover shows every column of the row

    uv run tutorials/quick_scatter.py data/funnel/scores.parquet --group pair --score total
    uv run tutorials/quick_scatter.py data/funnel/hearings.parquet --max-rows 50000

The point is speed: you don't write a plot for a schema; you dump the table and look.
"""
import argparse
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).parent))
from htmlkit import write_page  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("table")
ap.add_argument("--x")
ap.add_argument("--y")
ap.add_argument("--group", help="categorical column for colouring / best-per-group")
ap.add_argument("--score", help="numeric column that defines 'best' (max) per group")
ap.add_argument("--max-rows", type=int, default=100_000, help="random sample above this")
ap.add_argument("--out")
ap.add_argument("--plotly", default="cdn", choices=["cdn", "inline"])
a = ap.parse_args()

p = Path(a.table)
df = pl.read_parquet(p) if p.suffix == ".parquet" else pl.read_csv(p, infer_schema_length=10_000)
if df.height > a.max_rows:
    df = df.sample(a.max_rows, seed=0)
# nested / object columns can't go in a scatter; stringify them for hover
df = df.with_columns([pl.col(c).cast(pl.String) for c, t in df.schema.items()
                      if t.is_nested() or t == pl.Object])
num = [c for c, t in df.schema.items() if t.is_numeric()]
if not num:
    sys.exit("no numeric columns")
print(df.schema)
cols = {c: df[c].to_list() for c in df.columns}
data = dict(cols=cols, num=num, all=df.columns, x=a.x or num[0], y=a.y or num[min(1, len(num) - 1)],
            group=a.group, score=a.score, n=df.height)

opts = "".join(f"<option>{c}</option>" for c in num)
gopts = "<option value=''>(none)</option>" + "".join(f"<option>{c}</option>" for c in df.columns)
body = f"""
<div class="panel">
 <label>x <select id="x">{opts}</select></label>
 <label>y <select id="y">{opts}</select></label>
 <label>colour <select id="c"><option value=''>(none)</option>{opts}</select></label>
 <label>group <select id="g">{gopts}</select></label>
 <label>score <select id="s"><option value=''>(none)</option>{opts}</select></label><br>
 <label><input type=checkbox id="bygroup"> colour by group</label>
 <label><input type=checkbox id="best"> only best row per group (max score)</label>
 <label>filter <select id="fcol">{opts}</select></label>
 <input type=range id="flo" min=0 max=1000 value=0> <input type=range id="fhi" min=0 max=1000 value=1000>
 <span class="val" id="frange"></span>
 <div id="status" style="color:#999;margin-top:6px"></div>
</div>
<div id="plot" style="height:720px"></div>
"""

js = r"""
const el = id => document.getElementById(id), C = DATA.cols, N = DATA.n;
el("x").value = DATA.x; el("y").value = DATA.y;
if (DATA.group) { el("g").value = DATA.group; el("bygroup").checked = true; }
if (DATA.score) { el("s").value = DATA.score; el("best").checked = !!DATA.group; }
const PAL = ["#e6194b","#3cb44b","#ffe119","#4363d8","#f58231","#911eb4","#46f0f0","#f032e6","#bcf60c","#fabebe",
             "#008080","#e6beff","#9a6324","#fffac8","#800000","#aaffc3","#808000","#ffd8b1","#000075","#808080"];
const minmax = a => { let lo = Infinity, hi = -Infinity; for (const v of a) if (v != null) { if (v < lo) lo = v; if (v > hi) hi = v; } return [lo, hi]; };
const hover = [...Array(N).keys()].map(i => DATA.all.map(k => `${k}: ${C[k][i]}`).join("<br>"));

function rows() {
  const fc = C[el("fcol").value], [lo, hi] = minmax(fc);
  const a = lo + (hi - lo) * el("flo").value / 1000, b = lo + (hi - lo) * el("fhi").value / 1000;
  el("frange").textContent = `${a.toPrecision(5)} .. ${b.toPrecision(5)}`;
  let idx = [...Array(N).keys()].filter(i => fc[i] == null || (fc[i] >= a && fc[i] <= b));
  const g = el("g").value, s = el("s").value;
  if (el("best").checked && g && s) {              // keep argmax(score) per group
    const best = new Map();
    for (const i of idx) { const k = C[g][i]; if (!best.has(k) || C[s][i] > C[s][best.get(k)]) best.set(k, i); }
    idx = [...best.values()];
  }
  return idx;
}

function draw() {
  const idx = rows(), x = el("x").value, y = el("y").value, g = el("g").value, c = el("c").value;
  const marker = {size: 6, opacity: 0.85};
  let ngroups = 0;
  if (el("bygroup").checked && g) {
    const keys = new Map(); idx.forEach(i => { if (!keys.has(C[g][i])) keys.set(C[g][i], keys.size); });
    ngroups = keys.size;
    marker.color = idx.map(i => PAL[keys.get(C[g][i]) % PAL.length]);
  } else if (c) {
    marker.color = idx.map(i => C[c][i]); marker.colorscale = "Viridis"; marker.showscale = true;
    marker.colorbar = {title: {text: c}};
  }
  const tr = {type: idx.length > 20000 ? "scattergl" : "scatter", mode: "markers",
              x: idx.map(i => C[x][i]), y: idx.map(i => C[y][i]), text: idx.map(i => hover[i]),
              hovertemplate: "%{text}<extra></extra>", marker};
  Plotly.react("plot", [tr], {paper_bgcolor: "#16181d", plot_bgcolor: "#1b1e24", font: {color: "#ccc"},
    xaxis: {title: {text: x}, gridcolor: "#333"}, yaxis: {title: {text: y}, gridcolor: "#333"}, margin: {t: 20}, uirevision: x + y});
  el("status").textContent = `${idx.length} of ${N} rows shown` + (ngroups ? `, ${ngroups} groups` : "");
}
document.querySelectorAll("select,input").forEach(e => e.addEventListener("input", draw));
draw();
"""

out = a.out or p.with_suffix(".scatter.html")
write_page(out, f"{p.name}", body, data, js, a.plotly)
print("wrote", out)
