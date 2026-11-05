# Plotly, as throwaway interactive HTML pages

**What it is:** Plotly is an interactive plotting library. **plotly.js** runs in the browser, and
**plotly.py** builds figures in Python and writes them out as HTML/JSON. Both are MIT-licensed. The
output is a browser page, so it works on Linux with no IDE.

- Python: <https://plotly.com/python/>
- JS function reference (`newPlot`, `react`, `restyle`, `relayout`):
  <https://plotly.com/javascript/plotlyjs-function-reference/>

## What he's actually doing

The frames at 7:14, 9:19, 18:32, 21:31 (and 22:34) all show the Plotly modebar (camera, zoom, pan,
box/lasso, autoscale, home). The controls around the plots, though, are **plain HTML** inputs, not
Plotly's own slider widget:

| Frame | Page | Controls |
|---|---|---|
| ![](../frames/7_14.jpg) 7:14 | *CPA Timeline* | `<input type=number>` window length (920) + range slider "slide window"; live `left =` / `right =` text |
| ![](../frames/9_19.jpg) 9:19 | *Doppler Curve Fit* | 4 range sliders (f0, v, d, t0) driving a red model curve over a dB heatmap; computed readouts f_pre / f_post / max RoC; **"Take snapshot" log** with MIN/MAX/BEST |
| ![](../frames/18_32.jpg) 18:32 | *Right vs Wrong Model* | **checkboxes** toggling two model curves + Δt / f0 sliders; annotations "delayed-CPA from measurement / from flight geometry" |
| ![](../frames/21_31.jpg) 21:31 | *Event1 vs Event2 Score* | checkboxes "color by flight-pair combo" / "show only best point per combo"; a status line "41 unique flight-pair combos (of 195)" |

The pages above share one recipe: **Python computes the data, dumps it as JSON into one `.html`
file, and a few dozen lines of JavaScript wire `<input>` elements to `Plotly.restyle` /
`Plotly.react`.** His script names show it: `doppler explorer html drag point and…`,
`offset html visualize`, `histo html for one fl…`, `locked time visualiz…`, `html location curve`.
Claude Code is in his VS Code status bar, so these pages were very likely AI-written on demand.
(15:17 and 15:48 are polished explainer pages made for the video; I skipped them as you asked.)

**Habits worth copying:**

1. **One disposable page per question.** He doesn't build a dashboard; each page answers one thing
   and gets thrown away.
2. **The page says where its data came from.** The 21:31 subtitle reads: *"Every surviving
   candidate from 1_2b_v7.py's own final output. x = this candidate's event1 score, y = …
   (both from curve_match_scores_locked_spectrogram …)"*. Six weeks later you'll know what you were
   looking at.
3. **Snapshot logs.** The 9:19 page records slider positions as you find "still plausible" fits, then
   computes MIN/MAX. That's how he got *ranges* instead of point estimates.
4. **Counts on screen.** "41 of 195 shown": always show how many rows survive the current toggles.

## Three tiers of interactivity: pick the cheapest that works

| Tier | Mechanism | Good for | Limits |
|---|---|---|---|
| **1. Native Plotly controls** | `layout.sliders`, `layout.updatemenus` (buttons/dropdowns), `frames` + animation. Each step calls `restyle` / `relayout` / `update` / `animate` with **precomputed** args | Toggling traces, stepping one discrete parameter, animating time; pure Python, zero JS | Every state is baked into the file; no continuous models; no checkboxes |
| **2. Python → HTML + JS** | Python writes JSON; JS calls `Plotly.restyle(gd, update, traceIdx)`, `Plotly.react`, listens to `plotly_click` / `plotly_selected` | Continuous models (Doppler fit), checkboxes, derived readouts, click-to-trace; one portable file, no server | You write (or have an LLM write) ~50 lines of JS |
| **3. Python-reactive** | **marimo** (`mo.ui.slider`, `mo.ui.table`), or Jupyter + `go.FigureWidget` + ipywidgets, or Dash/Panel | Any Python per interaction: refit, re-query Polars, recompute a spectrogram | Needs a running Python process |

My suggestion for quick-and-dirty exploration: **start in marimo** (tier 3), because changing a
question is just editing a cell. **Freeze into a tier-2 HTML** once you'd look at it again or want
to send it to someone.

### API notes that save hours

- `Plotly.restyle(gd, {x: [xs1, xs2], y: [ys1, ys2]}, [1, 2])`: data attributes take
  **array-of-arrays**, one per trace index. `{x: xs}` without the outer array is the classic bug.
- **Titles are objects:** `xaxis: {title: {text: "Hz"}}`, not `title: "Hz"`. plotly.js 3+ silently
  drops the bare-string form. I hit this too: every axis label vanished when the page loaded a newer
  plotly.js than the one I'd tested against. Pin the plotly.js version to the one bundled with your
  plotly.py (`plotly.offline.get_plotlyjs_version()`), as `htmlkit.py` does.
- `layout.uirevision = "anything"` keeps the user's zoom and pan while you redraw from sliders.
- Use `scattergl` past about 20k points.
- **Heatmaps bloat files.** A 1000×1000 float heatmap is about 6 MB of JSON. Crop to the band of
  interest, decimate, or quantize to uint8 and base64-encode it (`tutorials/htmlkit.py: pack_u8`).
  In Python, `px.imshow(..., binary_string=True)` does something similar.
- **Datetimes:** give shapes, annotations, and traces the *same kind* of x value. I hit this one
  myself: traces used naive-UTC datetimes and a shape used epoch-ms, and the shape landed 7 hours
  off because the browser applied its local timezone. The fix is in `tutorials/native_controls.py`.
- `customdata` + `hovertemplate` (or a precomputed `text` per point) puts every column of the row in
  the hover. That's essential when you don't know which column matters yet.
- `fig.write_html(path, include_plotlyjs="cdn")` for a small file, or `True` to embed plotly.js
  (~4.5 MB, works offline). `full_html=False` gives a `<div>` to drop into your own template, and
  `post_script=` injects JS that can reference the figure.
- Plotly ≥ 6 accepts **Polars DataFrames** directly in `plotly.express` (via narwhals).

### Quick-and-dirty Plotly Express for a table you don't understand yet (`uv run --with polars,pyarrow,plotly,numpy ipython`)

```python
import polars as pl, plotly.express as px
df = pl.read_parquet("data/funnel/hearings.parquet")
px.scatter_matrix(df, dimensions=["r", "t_dcpa", "gs_ms"], color="type_code").show()
px.histogram(df, x="r", color="type_code", facet_col="type_code", facet_col_wrap=4).show()
px.density_heatmap(df, x="t_dcpa", y="r", nbinsx=200).show()
px.scatter(df.sample(20000), x="t_dcpa", y="r", color="gs_ms", hover_data=df.columns).show()
```

`tutorials/quick_scatter.py` does this generically. Point it at any parquet or CSV and you get
x/y/color dropdowns over every numeric column, plus group coloring, best-per-group, and a threshold
filter.

## Existing tutorials (the reactive parts, not "plot a line")

- **Native controls:** [Sliders](https://plotly.com/python/sliders/),
  [Custom Buttons](https://plotly.com/python/custom-buttons/) (restyle vs relayout vs update),
  [Dropdowns](https://plotly.com/python/dropdowns/),
  [Animations](https://plotly.com/python/animations/).
- **JS reactivity:** [plotly.js function reference](https://plotly.com/javascript/plotlyjs-function-reference/)
  (read `react`, `restyle`, `relayout`, `extendTraces`) and
  [plotly.js events](https://plotly.com/javascript/plotlyjs-events/) (`plotly_click`,
  `plotly_selected`, `plotly_relayout`).
- **Python-reactive:** [FigureWidget](https://plotly.com/python/figurewidget/) (Jupyter),
  [marimo docs](https://docs.marimo.io/) (start with the
  [slider](https://docs.marimo.io/api/inputs/slider/) and the "interactive elements" guide).
- **Export:** [Interactive HTML export](https://plotly.com/python/interactive-html-export/).

## Tutorials in this repo (all tested)

Run `uv run tutorials/make_dataset.py --out data`, `uv run tutorials/polars_funnel.py data`, and
`uv run tutorials/score_candidates.py data` first. Every script has inline dependencies, so
`uv run` builds the environment for you.

### A. Native controls, no JS: `native_controls.py` (re-creates 7:14)

```sh
uv run tutorials/native_controls.py data && xdg-open cpa_timeline.html
```

- **Read:** how each slider step is a `relayout` with a new `shapes` list, and each button is a
  `restyle` of `visible`.
- **Exercise 1:** add a second slider that changes the *window length* (900, 910, … 940 s). Notice
  you need one step per combination, which shows why tier 1 doesn't scale to continuous parameters.
- **Exercise 2:** turn the timeline into an animation (`frames=[go.Frame(...)]`) that slides the
  window across the day, with a play button.

### B. Live model on data: `doppler_explorer.py` (re-creates 9:19)

```sh
uv run tutorials/doppler_explorer.py data/recording.wav --t0 130 --t1 330 --fmax 450 --whiten
```

- **Read:** `model()` in the JS (retarded-time Doppler), `redraw()` (one `restyle` of 8 curve
  traces, never re-sending the heatmap), `plotly_click` → trace points, and URL presets
  (`doppler_fit.html?f0=96&v=56&d=1800&tc=231` is also a shareable "permalink" of a fit).
- **Exercise 1 (re-create 18:32):** add a "naive model" checkbox. The naive model uses the plane's
  radial velocity at the *hearing* time instead of the emission time. Plot both and convince yourself
  the naive curve isn't just the right curve shifted.
- **Exercise 2:** add MIN/MAX/BEST rows to the snapshot table, like his.
- **Exercise 3:** fit the clicked trace inside the page (a 40-line Nelder–Mead in JS), or skip that
  and pipe "Copy trace CSV" into `uv run tutorials/fit_trace.py`.

### C. Any table → explorer: `quick_scatter.py` (re-creates 21:31)

```sh
uv run tutorials/quick_scatter.py data/funnel/scores.parquet --x score1 --y score2 --group pair --score total
uv run tutorials/quick_scatter.py data/funnel/hearings.parquet       # a table you haven't looked at yet
```

- Tick "best row per group" and the true flight pair separates in the top right, as in the video.
- **Exercise:** add a histogram mode (switch the trace type to `histogram` on the x column), and a
  lasso → `plotly_selected` → CSV of the selected rows.

### D. Candidate curves vs spectrogram: `score_candidates.py` → `compare.html` (re-creates 21:40–22:34)

- Checkboxes toggle each candidate's harmonics over both events; event 2 is *locked* by flight
  geometry.
- **Notice:** candidate #2's curves are jagged. That decoy reports every 2–5 s with timestamp
  jitter, and differentiating raw positions amplifies noise. **Exercise:** smooth the track before
  differentiating (`scipy.interpolate.make_smoothing_spline` per axis) and see whether the scores
  change.

### E. Python-reactive: `doppler_marimo.py`

```sh
uvx marimo edit --sandbox tutorials/doppler_marimo.py -- --data data
```

- Moving the f0 slider re-runs only the plot cell. Changing the FFT size re-runs the spectrogram
  cell. Selecting rows in the candidate table maps them.
- **Exercise:** add a cell that re-runs `fit_trace`-style least squares whenever you change the
  window, and draws the fitted curve in a second color. You can't do that in tier 2 without porting
  the fit to JS, and that's the whole argument for tier 3.
