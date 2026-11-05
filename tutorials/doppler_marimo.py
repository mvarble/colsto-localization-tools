# /// script
# requires-python = ">=3.11"
# dependencies = ["marimo", "numpy", "scipy", "polars", "pyarrow", "plotly"]
# ///
"""
Tier 3: Python-reactive exploration with marimo. No IDE, no JS, no server code.

    uvx marimo edit --sandbox tutorials/doppler_marimo.py -- --data data   # opens in your browser
    uvx marimo run  --sandbox tutorials/doppler_marimo.py -- --data data   # read-only "app" view

Every cell re-runs automatically when a UI element it reads changes. Moving a slider re-runs only
the cells downstream of it -- the spectrogram cell does NOT recompute when you move f0.
"""
import marimo

__generated_with = "0.9.0"
app = marimo.App(width="full")


@app.cell
def _():
    import sys
    from pathlib import Path

    import marimo as mo
    import numpy as np
    import plotly.graph_objects as go
    import polars as pl

    sys.path.insert(0, str(Path(__file__).parent))
    from htmlkit import load_wav, spec_db

    DATA = Path(mo.cli_args().get("data") or "data")
    if not (DATA / "recording.wav").exists():
        DATA = Path(__file__).parent.parent / "data"
    fs, audio = load_wav(DATA / "recording.wav")
    C = 343.0
    return C, DATA, Path, fs, audio, go, load_wav, mo, np, pl, spec_db, sys


@app.cell
def _(audio, fs, mo):
    window = mo.ui.range_slider(start=0, stop=len(audio) / fs, step=5, value=[130, 330],
                                label="window (s)", full_width=True)
    nfft = mo.ui.dropdown(["1024", "2048", "4096", "8192", "16384"], value="4096", label="FFT size")
    fmax = mo.ui.slider(100, 2000, step=50, value=500, label="f max (Hz)", show_value=True)
    whiten = mo.ui.checkbox(value=True, label="whiten rows")
    mo.vstack([window, mo.hstack([nfft, fmax, whiten], justify="start")])
    return fmax, nfft, whiten, window


@app.cell
def _(audio, fmax, fs, nfft, spec_db, whiten, window):
    # depends only on the spectrogram controls -> not re-run when model sliders move
    t, f, Z = spec_db(audio, fs, window.value[0], window.value[1], 40, fmax.value, int(nfft.value),
                      whiten=whiten.value)
    return Z, f, t


@app.cell
def _(mo, window):
    f0 = mo.ui.slider(40, 400, step=0.5, value=96, label="f0 Hz", show_value=True, full_width=True)
    v = mo.ui.slider(10, 250, step=0.5, value=56, label="v m/s", show_value=True, full_width=True)
    d = mo.ui.slider(100, 8000, step=10, value=1800, label="d m", show_value=True, full_width=True)
    tc = mo.ui.slider(window.value[0], window.value[1], step=0.1, value=sum(window.value) / 2,
                      label="t0 (delayed CPA) s", show_value=True, full_width=True)
    nh = mo.ui.slider(1, 6, value=4, label="harmonics", show_value=True)
    mo.vstack([f0, v, d, tc, nh])
    return d, f0, nh, tc, v


@app.cell
def _(C, np):
    def doppler(f0, v, d, tc, span):
        """Straight-line pass, retarded time. Returns heard time and frequency."""
        te_c = tc - d / C
        te = np.linspace(te_c - span, te_c + span, 1500)
        x = v * (te - te_c)
        R = np.hypot(x, d)
        return te + R / C, f0 * C / (C + v * x / R)
    return (doppler,)


@app.cell
def _(Z, d, doppler, f, f0, go, mo, nh, t, tc, v):
    fig = go.Figure(go.Heatmap(x=t, y=f, z=Z, colorscale="Viridis", showscale=False))
    _tt, _ff = doppler(f0.value, v.value, d.value, tc.value, span=t[-1] - t[0])
    _in = (_tt >= t[0]) & (_tt <= t[-1])
    for _k in range(1, nh.value + 1):          # _names are cell-local in marimo
        fig.add_scatter(x=_tt[_in], y=_k * _ff[_in], mode="lines", line=dict(color="red", width=1.5),
                        name=f"h{_k}", showlegend=False)
    fig.update_layout(template="plotly_dark", height=520, margin=dict(t=10, b=40),
                      xaxis_title="recording time (s)", yaxis_title="Hz", uirevision="keep")
    C0 = 343.0
    mo.vstack([mo.md(f"**f_pre** {f0.value*C0/(C0-v.value):.1f} Hz &nbsp; **f_post** "
                     f"{f0.value*C0/(C0+v.value):.1f} Hz"), fig])
    return (fig,)


@app.cell
def _(DATA, mo, pl):
    # Linked views: pick rows in a table, downstream cells see the selection as a DataFrame
    _p = DATA / "funnel" / "scores.parquet"
    scores = (pl.read_parquet(_p).select("pair", "total", "score1", "score2", "lat", "lon", "r", "r_2")
              .sort("total", descending=True)) if _p.exists() else pl.DataFrame()
    table = mo.ui.table(scores, selection="multi", page_size=8, label="candidates (select rows)")
    table
    return scores, table


@app.cell
def _(go, mo, table):
    _sel = table.value
    if _sel is not None and len(_sel):
        _out = go.Figure(go.Scattermap(lat=_sel["lat"].to_list(), lon=_sel["lon"].to_list(), mode="markers",
                                       marker=dict(size=12), text=_sel["pair"].to_list()))
        _out.update_layout(map=dict(style="open-street-map", zoom=11,
                                    center=dict(lat=_sel["lat"].mean(), lon=_sel["lon"].mean())),
                           height=400, margin=dict(l=0, r=0, t=0, b=0))
    else:
        _out = mo.md("_select rows above to map them_")
    _out
    return


if __name__ == "__main__":
    app.run()
