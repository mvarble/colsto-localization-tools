# Learning the tools from "I discovered a sound that leaks your exact location"

This breaks down the tools the presenter uses to geolocate a security-camera recording by matching
aircraft Doppler curves against ADS-B data. Each tool gets a doc (what it is, how he uses it, what
else it can do, existing tutorials, and a tutorial of mine). There's also a runnable synthetic
version of his whole problem to practice on.

Everything here runs on Linux. Every IDE-bound tool has a terminal or standalone alternative.

## His problem, broken into parts (from the transcript)

| # | Question | Tools seen | When |
|---|---|---|---|
| 1 | Is there anything in this audio? | **AudioLens** spectrogram in VS Code: zoom band, raise resolution | 1:06–2:40 |
| 2 | Get every flight over the US that day | **Flightradar24 API** via **pyfr24**; viewed in **QGIS** | 2:50–3:30 |
| 3 | Prop planes only | **ICAO Doc 8643** type table → remove known jets (**Polars**) | 3:30–4:10 |
| 4 | Where would each place hear each flight, and when? | 200 m grid × tracks → CPA, slant range (DEM), **delayed** CPA (Python/Polars), checked in **QGIS** | 4:10–6:40 |
| 5 | Heard a plane, then another 920 s later? | offset filter; **Plotly + HTML** "CPA Timeline" | 6:40–8:00 |
| 6 | Measure speed and distance from each curve | **Plotly + HTML** "Doppler Curve Fit" sliders | 8:30–10:30 |
| 7 | Speed + distance + silence filters | Polars; **QGIS** reveals airports → silence filter | 10:30–13:00 |
| 8 | Model the *exact* curve per candidate and score it | retarded-time Doppler, locked scoring; **Plotly + HTML** checks | 13:30–21:00 |
| 9 | Rank, refine, verify | **Plotly** score scatter, **QGIS** fine heat map, Google Street View | 21:00–26:00 |
| 10 | "Can you defend against it?" | **Audacity**: high-pass, MP3, re-boost | 26:00–27:00 |

## Tool docs

| Tool | Doc | Linux | IDE-free / alternative |
|---|---|---|---|
| QGIS | [docs/qgis.md](docs/qgis.md) | yes | it's a standalone app |
| AudioLens (VS Code ext.) | [docs/audiolens.md](docs/audiolens.md) | yes (VS Code/VSCodium) | **Sonic Visualiser**; **inspectrum** for IQ |
| Plotly + throwaway HTML pages | [docs/plotly-html.md](docs/plotly-html.md) | yes (browser) | marimo in the browser |
| Polars (+ DuckDB) | [docs/polars.md](docs/polars.md) | yes | **DuckDB CLI** |
| Audacity | [docs/audacity.md](docs/audacity.md) | yes | — |
| PyCharm (and his script habits) | [docs/pycharm.md](docs/pycharm.md) | yes | `uv run` scripts, ipython, marimo, `entr` |
| Flightradar24 / pyfr24 / Doc 8643 / DEM | [docs/flight-data.md](docs/flight-data.md) | — | adsb.lol, OpenSky, your own RTL-SDR, SatNOGS |

**Skipped** as you asked: the explainer pages at 15:17 and 15:48 (made for the video, not for
analysis) and the slide at 12:10. **Confidence:** AudioLens, QGIS, Audacity, PyCharm, Polars,
pyfr24, and Doc 8643 are identified directly from the frames. That the Plotly pages are
Python-generated HTML with plain-JS controls is an inference from the frames and his script names;
it's consistent with everything visible.

## The skill he's actually using

Look at his layer tree (`post offset`, `post silence`, `old`, `old`) and his script names
(`check jets in output`, `1.2a v9` → `v10`, `offset html visualize`). The loop is:

1. **Ask one question** ("did anything fly over between the two events?").
2. **Answer it with a small script** that writes a file (Parquet/CSV/GPKG/HTML), brute-force first.
3. **Look at the result in the tool that suits it:** a map for space, a throwaway Plotly page for
   time and parameters, a spectrogram viewer for the raw signal.
4. **Compare survivors with real-world context.** That's where the next question comes from (the
   airports → the silence filter; the curve misfit → modeling the exact geometry).
5. Keep every stage as its own layer or file, so you can toggle back and see what each filter
   removed.

The tutorials train exactly this loop.

## Quick start (all tested on this machine)

Needs only [`uv`](https://docs.astral.sh/uv/). Every script declares its own dependencies.

```sh
uv run tutorials/make_dataset.py --out data          # synthetic recording + messy nested flight table (+ TRUTH.json; don't peek)
uv run tutorials/doppler_explorer.py data/recording.wav --t0 130 --t1 330 --fmax 450 --whiten   # -> doppler_fit.html
uv run tutorials/fit_trace.py --demo                 # traced points -> f0, v, d, t0 with uncertainties
uv run tutorials/polars_funnel.py data               # the funnel: 14,491 -> 89 -> 31 points, 6 flight pairs (~1 min)
uv run tutorials/score_candidates.py data            # curve scoring: true pair wins; fine-grid best point ~23 m from truth
uv run tutorials/quick_scatter.py data/funnel/scores.parquet --x score1 --y score2 --group pair --score total
uv run tutorials/native_controls.py data             # pure-Python Plotly slider/buttons -> cpa_timeline.html
uvx marimo edit --sandbox tutorials/doppler_marimo.py -- --data data    # Python-reactive notebook in the browser
```

Then open `data/recording.wav` in Sonic Visualiser or Audacity, and `data/funnel/*.gpkg` in QGIS,
following each doc's tutorial.

### The synthetic dataset (`tutorials/make_dataset.py`)

- `recording.wav`: 23 minutes at 8 kHz. Two faint prop-plane flyovers 920 s apart, under wind
  rumble, gusts, mains hum, and birds. They're rendered with the exact retarded-time model, and the
  first plane accelerates and turns slightly, so its curve doesn't fit a straight-line model on both
  sides, as in the video.
- `flights.parquet`: 262 flights in an FR24-like **nested** schema
  (`flight_trail_list: list[struct]`). It has duplicates, mixed 1/2/5 s cadence, null types, and
  altitude dropouts, plus a busy GA airport that produces false candidates.
- `aircraft_types.csv`: a Doc 8643-style lookup with deliberate gaps.
- `TRUTH.json`: the answer.

## Suggested order

1. [audiolens.md](docs/audiolens.md) tutorial (find and measure the curves) → `fit_trace.py`
2. [polars.md](docs/polars.md) (funnel) together with [qgis.md](docs/qgis.md) (look at each stage)
3. [plotly-html.md](docs/plotly-html.md) tiers A → E
4. [audacity.md](docs/audacity.md) (attenuation is not deletion)
5. The capstones in [flight-data.md](docs/flight-data.md): your own 1090 MHz receiver plus a mic,
   or SatNOGS satellite Doppler with the station location hidden

## Layout

```
README.md            this file
docs/                one doc per tool
frames/              the stills I used as evidence (scaled down)
tutorials/           runnable, self-contained (PEP 723) scripts; htmlkit.py = shared HTML/spectrogram helper
data/                generated by make_dataset.py (safe to delete and regenerate)
```
