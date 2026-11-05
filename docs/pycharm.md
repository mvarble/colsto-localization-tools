# PyCharm, and how to get the same workflow without an IDE

**What it is:** PyCharm is JetBrains' Python IDE (<https://www.jetbrains.com/pycharm/>) and runs on
Linux. It's what he writes his scripts in at 3:12. You can tell from the JetBrains "new UI" layout,
the `Project ▾` dropdown, the memory indicator (`974 of 2200M`), and the interpreter badge
`Python 3.14 (Planev2)`. VS Code shows up too (1:24), with Claude Code in its status bar.

**The IDE isn't the part worth copying. His working habits are**, and they work from a terminal.

## What his project tree tells you (3:12)

About 60 scripts under `Planev2/scripts/`, named as **questions or actions**, not modules:

- `check jets in output.py`, `check for point in 1.…`, `csv check.py`, `check 1.2a.py`: quick
  verification scripts
- `funnel charts.py`, `histo html for one fl…`, `offset html visualize.py`,
  `locked time visualiz…`, `doppler explorer html drag point and…`: one throwaway page per question
- `1.1 v8 CRS fix.py`, `1.1b v2 aggregate.py`, `1.2a v9.py`, `1.2a v10.py`: pipeline stages,
  **versioned by copying** so the old version stays runnable
- `can delete - DEM t…`, `can delete - metrics…`, `can delete - yt dlp…`: a naming convention that
  marks dead ends instead of deleting them
- `notes.py`, `profile scoring.py`, `matching_shared.py`: notes, a profiling script, and one shared
  helper module

The pattern: **small scripts that read files and write files** (CSV, Parquet, GPKG, HTML). Each
output is opened in whichever tool suits it (QGIS, a browser, an audio viewer). Nothing is a
long-lived app.

## The same workflow without an IDE

| Need | Terminal-native option |
|---|---|
| Per-script dependencies, nothing to activate | `uv run script.py` with [inline script metadata](https://docs.astral.sh/uv/guides/scripts/) (`# /// script` header). Every tutorial here uses it. |
| Run cell by cell | `# %%` markers work in `ipython` (`%run -i script.py`) and convert to notebooks with `jupytext`. |
| Re-run on save | `ls *.py \| entr -c uv run funnel.py data` (or `watchexec`) |
| Reactive notebook in the browser | `uvx marimo edit --sandbox notebook.py`. See [plotly-html.md](plotly-html.md). |
| Look at a data file now | `duckdb -c "SUMMARIZE 'x.parquet'"`. See [polars.md](polars.md). |
| Look at audio | Sonic Visualiser. See [audiolens.md](audiolens.md). |
| Generate the throwaway HTML explorer | Claude Code (or any LLM) from the terminal: "write a single-file HTML page that loads X.json and lets me slide Y and Z". `tutorials/htmlkit.py` is a template to point it at. |

## A habit list to steal

1. One script = one question. Name it as the question.
2. Version by copying (`v9`, `v10`) when an experiment changes the logic; mark dead ends instead of
   deleting them.
3. Write intermediate results to files, one per funnel stage, so every stage can be opened in QGIS or
   a page.
4. Put data-quality discoveries in docstrings where the code depends on them (his FR24 ID-recycling
   note).
5. Have every page say which script produced it.
