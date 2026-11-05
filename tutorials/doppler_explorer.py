# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "scipy", "plotly"]
# ///
"""
Re-creation of the video's "Doppler Curve Fit" page (9:19): one static HTML file,
spectrogram heatmap + a live Doppler model driven by four sliders. No server.

    uv run tutorials/doppler_explorer.py data/recording.wav --t0 120 --t1 340 --fmax 500
    xdg-open doppler_fit.html

Model (straight line, constant speed, *retarded time*):
    plane at x(te) = v (te - tc) along track, CPA slant distance d
    heard at       t  = te + R(te)/c,   R = sqrt(x^2 + d^2)
    frequency      f  = f0 * c / (c + v_away),  v_away = v x / R
    slider "t0"    = when the CPA emission is *heard*  (= tc + d/c), i.e. the delayed CPA time

What to learn from it:
  * v sets the size of the drop (f_pre/f_post), d sets how quickly it happens.
  * The fit is never perfect on both sides -- that misfit is real flight geometry (speed/heading change),
    which is exactly the information the video later exploits.
  * Click the spectrogram to drop trace points along a faint curve; "copy trace" gives CSV for a real fit.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from htmlkit import load_wav, pack_u8, spec_db, write_page  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("wav")
ap.add_argument("--t0", type=float, default=120)
ap.add_argument("--t1", type=float, default=340)
ap.add_argument("--fmin", type=float, default=40)
ap.add_argument("--fmax", type=float, default=500)
ap.add_argument("--nperseg", type=int, default=4096, help="FFT size: bigger = finer Hz, blurrier time")
ap.add_argument("--whiten", action="store_true", help="z-score each frequency row (kills hum lines)")
ap.add_argument("--out", default="doppler_fit.html")
ap.add_argument("--plotly", default="cdn", choices=["cdn", "inline"])
a = ap.parse_args()

fs, x = load_wav(a.wav)
t, f, D = spec_db(x, fs, a.t0, a.t1, a.fmin, a.fmax, a.nperseg, whiten=a.whiten)
print(f"spectrogram {D.shape[0]} freq x {D.shape[1]} time bins, df={f[1]-f[0]:.2f} Hz, dt={t[1]-t[0]:.3f} s")

data = {"t": [round(v, 3) for v in t], "f": [round(v, 2) for v in f], "z": pack_u8(D),
        "t0": a.t0, "t1": a.t1, "fmin": a.fmin, "fmax": a.fmax}

mid = (a.t0 + a.t1) / 2
body = f"""
<div class="panel">
 <div><label>f0 (Hz)</label><input id="f0" type="range" min="{a.fmin}" max="{a.fmax}" step="0.1" value="{(a.fmin+a.fmax)/3:.1f}"><span class="val" id="f0v"></span></div>
 <div><label>v (m/s)</label><input id="v" type="range" min="10" max="250" step="0.5" value="80"><span class="val" id="vv"></span></div>
 <div><label>d slant (m)</label><input id="d" type="range" min="100" max="10000" step="10" value="2500"><span class="val" id="dv"></span></div>
 <div><label>t0 delayed CPA (s)</label><input id="tc" type="range" min="{a.t0}" max="{a.t1}" step="0.05" value="{mid:.2f}"><span class="val" id="tcv"></span></div>
 <div><label><input id="harm" type="checkbox" checked> harmonics</label>
      <label>n = <input id="nh" type="number" min="1" max="8" value="3" style="width:40px"></label>
      <label><input id="showtrace" type="checkbox" checked> trace points</label>
      <span style="color:#888">keyboard: focus a slider, then arrow keys for fine steps</span></div>
</div>
<div class="panel" id="readout"></div>
<div id="plot" style="height:620px"></div>
<div class="panel">
 <button id="snap">Take snapshot</button><button id="clear">Clear log</button>
 <button id="copytrace">Copy trace CSV</button><button id="cleartrace">Clear trace</button>
 <span style="color:#888">click on the spectrogram to add trace points</span>
 <table id="log"><tr><th>f0</th><th>v</th><th>d</th><th>t0</th><th>f_pre</th><th>f_post</th></tr></table>
</div>
"""

js = r"""
const C = 343.0;
const z = unpackU8(DATA.z);
const el = id => document.getElementById(id);
const trace = [];  // clicked points
// presets / permalink: doppler_fit.html?f0=96&v=56&d=1800&tc=231
new URLSearchParams(location.search).forEach((val, key) => { if (el(key)) el(key).value = val; });
function permalink() {
  const q = ["f0", "v", "d", "tc"].map(k => k + "=" + el(k).value).join("&");
  history.replaceState(null, "", "?" + q);
}

function model(f0, v, d, tc, k) {
  // sample emission times so the curve spans the window; return heard time + frequency
  const te_c = tc - d / C, xs = [], ys = [];
  const span = (DATA.t1 - DATA.t0) * 1.2;
  for (let i = 0; i <= 600; i++) {
    const te = te_c - span + (2 * span * i) / 600;
    const xx = v * (te - te_c), R = Math.hypot(xx, d);
    const t = te + R / C;
    if (t < DATA.t0 || t > DATA.t1) continue;
    xs.push(t); ys.push(k * f0 * C / (C + v * xx / R));
  }
  return [xs, ys];
}

function curves() {
  const f0 = +el("f0").value, v = +el("v").value, d = +el("d").value, tc = +el("tc").value;
  const n = el("harm").checked ? +el("nh").value : 1, out = [];
  for (let k = 1; k <= 8; k++) {
    const [xs, ys] = k <= n ? model(f0, v, d, tc, k) : [[], []];
    out.push({x: xs, y: ys});
  }
  permalink();
  el("f0v").textContent = f0.toFixed(1) + " Hz"; el("vv").textContent = v.toFixed(1) + " m/s";
  el("dv").textContent = d.toFixed(0) + " m";   el("tcv").textContent = tc.toFixed(2) + " s";
  const fpre = f0 * C / (C - v), fpost = f0 * C / (C + v);
  // max |df/dt| at CPA for a straight pass: f0 * v^2 / (c d)
  el("readout").innerHTML = `f_pre (approach) <span class=val>${fpre.toFixed(2)} Hz</span>
     f_post (recede) <span class=val>${fpost.toFixed(2)} Hz</span>
     max RoC <span class=val>${(f0 * v * v / (C * d)).toFixed(3)} Hz/s</span>`;
  return out;
}

const heat = {type: "heatmap", x: DATA.t, y: DATA.f, z: z, colorscale: "Viridis", zsmooth: false,
              colorbar: {title: {text: "dB"}}, hovertemplate: "t=%{x:.2f}s<br>f=%{y:.1f}Hz<br>%{z:.1f}<extra></extra>"};
const mk = k => ({type: "scatter", mode: "lines", x: [], y: [], hoverinfo: "skip", showlegend: k == 0,
                  name: "model", line: {color: k == 0 ? "#ff3b3b" : "rgba(255,80,80,0.6)", width: k == 0 ? 2 : 1}});
const tr = {type: "scatter", mode: "markers", x: [], y: [], name: "trace", marker: {color: "white", size: 7, symbol: "x"}};
const layout = {paper_bgcolor: "#16181d", plot_bgcolor: "#16181d", font: {color: "#ccc"},
                margin: {l: 60, r: 20, t: 10, b: 50}, xaxis: {title: {text: "recording time (s)"}},
                yaxis: {title: {text: "frequency (Hz)"}, range: [DATA.fmin, DATA.fmax]}, legend: {x: 0, y: 1.08, orientation: "h"},
                uirevision: "keep"};   // keep zoom while sliders redraw
Plotly.newPlot("plot", [heat, ...[...Array(8).keys()].map(mk), tr], layout, {scrollZoom: true});

function redraw() {
  const cs = curves();
  // restyle only the 8 curve traces (indices 1..8): cheap, the heatmap isn't re-sent
  Plotly.restyle("plot", {x: cs.map(c => c.x), y: cs.map(c => c.y)}, [1, 2, 3, 4, 5, 6, 7, 8]);
}
["f0", "v", "d", "tc", "harm", "nh"].forEach(id => el(id).addEventListener("input", redraw));
redraw();

el("plot").on("plotly_click", ev => {
  const p = ev.points[0]; trace.push([p.x, p.y]); trace.sort((a, b) => a[0] - b[0]);
  Plotly.restyle("plot", {x: [trace.map(q => q[0])], y: [trace.map(q => q[1])]}, [9]);
});
el("showtrace").addEventListener("input", e => Plotly.restyle("plot", {visible: e.target.checked}, [9]));
el("cleartrace").onclick = () => { trace.length = 0; Plotly.restyle("plot", {x: [[]], y: [[]]}, [9]); };
el("copytrace").onclick = () => {
  const csv = "t_s,f_hz\n" + trace.map(q => q[0].toFixed(3) + "," + q[1].toFixed(2)).join("\n");
  navigator.clipboard.writeText(csv); alert(trace.length + " points copied");
};
el("snap").onclick = () => {
  const f0 = +el("f0").value, v = +el("v").value;
  el("log").insertAdjacentHTML("beforeend", `<tr><td>${f0}</td><td>${v}</td><td>${el("d").value}</td>
    <td>${el("tc").value}</td><td>${(f0*C/(C-v)).toFixed(2)}</td><td>${(f0*C/(C+v)).toFixed(2)}</td></tr>`);
};
el("clear").onclick = () => { el("log").querySelectorAll("tr:not(:first-child)").forEach(r => r.remove()); };
"""

write_page(a.out, f"Doppler Curve Fit -- {Path(a.wav).name} {a.t0:.0f}-{a.t1:.0f}s", body, data, js, a.plotly)
print("wrote", a.out, f"({Path(a.out).stat().st_size/1e6:.1f} MB)")
