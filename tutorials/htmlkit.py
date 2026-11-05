"""
Tiny helpers shared by the "Python writes a throwaway HTML page" tutorials.

The pattern (what the video's *.html explorers are):
  1. Python does the heavy lifting (load audio / tables, compute spectrograms, scores).
  2. Python dumps the data as JSON into a single self-contained .html file.
  3. A few dozen lines of JS wire plain <input>s (sliders, checkboxes, selects) to
     Plotly.react / Plotly.restyle, so the model updates live with no server.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import spectrogram


def load_wav(path):
    fs, x = wavfile.read(path)
    x = x.astype(np.float64)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if np.issubdtype(x.dtype, np.integer) or np.abs(x).max() > 1.5:
        x = x / 32768.0
    return fs, x


def spec_db(x, fs, t0, t1, fmin, fmax, nperseg=4096, hop=None, whiten=False):
    """Spectrogram of x[t0:t1] in dB, cropped to [fmin, fmax].

    whiten=True z-scores each frequency row (median/MAD): removes steady hum lines and the
    noise-floor tilt, which makes faint chirps pop out -- and makes "sum brightness along a
    curve" a fair score.
    """
    hop = hop or nperseg // 4
    s0, s1 = int(t0 * fs), int(t1 * fs)
    f, t, S = spectrogram(x[s0:s1], fs, window="hann", nperseg=nperseg, noverlap=nperseg - hop, mode="psd")
    k = (f >= fmin) & (f <= fmax)
    D = 10 * np.log10(S[k] + 1e-20)
    if whiten:
        med = np.median(D, axis=1, keepdims=True)
        mad = np.median(np.abs(D - med), axis=1, keepdims=True) + 1e-9
        D = (D - med) / (1.4826 * mad)
    return t + t0, f[k], D


def pack_u8(Z, lo=None, hi=None):
    """Quantise a 2-D array to uint8 + base64. ~8x smaller than JSON floats.

    Spectrogram heatmaps are what bloat these pages: 1000 x 1000 floats as JSON is ~6 MB.
    """
    lo = float(np.percentile(Z, 5)) if lo is None else lo
    hi = float(np.percentile(Z, 99.8)) if hi is None else hi
    q = np.clip((Z - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)
    return {"b64": base64.b64encode(q.tobytes()).decode(), "rows": q.shape[0], "cols": q.shape[1],
            "lo": lo, "hi": hi}


# JS counterpart of pack_u8: returns z as array-of-rows in original units
JS_UNPACK = """
function unpackU8(p) {
  const bin = atob(p.b64), n = bin.length, z = [];
  const scale = (p.hi - p.lo) / 255;
  for (let r = 0; r < p.rows; r++) {
    const row = new Array(p.cols);
    for (let c = 0; c < p.cols; c++) row[c] = p.lo + bin.charCodeAt(r * p.cols + c) * scale;
    z.push(row);
  }
  return z;
}
"""

CSS = """
body{font-family:system-ui,sans-serif;background:#16181d;color:#ddd;margin:16px}
h2{margin:4px 0 8px} .panel{background:#1f2229;border-radius:8px;padding:10px 14px;margin-bottom:10px}
label{margin-right:14px;white-space:nowrap} .panel>div>label:first-child{display:inline-block;width:160px} input[type=range]{width:340px;vertical-align:middle}
.val{display:inline-block;min-width:90px;font-family:monospace;color:#9cf}
table{border-collapse:collapse;font-family:monospace;font-size:12px} td,th{padding:2px 8px;border-bottom:1px solid #333}
button{background:#2b6cb0;color:white;border:0;border-radius:4px;padding:4px 10px;margin-right:6px;cursor:pointer}
select{background:#2a2d35;color:#ddd;border:1px solid #444}
"""


def write_page(path, title, body_html, data, js, plotly="cdn"):
    """Write a single self-contained HTML page. plotly='inline' embeds plotly.js (~4.5 MB) for offline use."""
    # Load the SAME plotly.js version either way (the one bundled with your plotly.py). Mixing versions
    # bites: plotly.js 3+ silently ignores bare-string titles (`title: "x"`); use `title: {text: "x"}`.
    from plotly.offline import get_plotlyjs, get_plotlyjs_version
    if plotly == "inline":
        plotly_tag = f"<script>{get_plotlyjs()}</script>"
    else:
        plotly_tag = f'<script src="https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js"></script>'
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>
{plotly_tag}<style>{CSS}</style></head><body>
<h2>{title}</h2>
{body_html}
<script>
const DATA = {json.dumps(data, separators=(",", ":"))};
{JS_UNPACK}
{js}
</script></body></html>"""
    Path(path).write_text(html)
    return path
