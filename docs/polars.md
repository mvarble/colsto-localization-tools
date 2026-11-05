# Polars (plus DuckDB as the SQL-first, IDE-free alternative)

**What it is:** Polars is a DataFrame library written in Rust with a Python API. It has a lazy query
engine (`scan_*` → optimize → `collect`), multithreaded execution, a streaming engine for data
larger than RAM, and first-class nested types (`list`, `struct`). It runs on Linux. `uv add polars`.

- Site: <https://pola.rs>
- User guide: <https://docs.pola.rs/user-guide/>
- API: <https://docs.pola.rs/api/python/stable/reference/>

![PyCharm with Polars at 3:12](../frames/3_12.jpg)

## How he uses it

- **Evidence (3:12):** `def explode_trail(table: pl.DataFrame) -> pl.DataFrame | None` does
  `table.select(["flightid", "flight_trail_list"]).explode("flight_trail_list").unnest("flight_trail_list")`.
  Each FR24 flight row carries a **nested list of track points**, and he flattens it to one row per
  point. He mentions "50 GB parquet files" at 2:01, which is the scale where lazy scans and streaming
  matter.
- **Data-quality notes are written into the code.** The `load_done_flights` docstring says FR24
  numeric IDs get **recycled** across different real-world flights, so he keys on
  `(flightid, target_ts)` and not on `flightid` alone. When you don't know the schema, the identifier
  you assume is unique often isn't.
- **Resumable downloads.** `append_track_log` / `append_tracks` append to CSV logs with
  `status == "ok"`, so a multi-hour scrape can restart.
- **The funnel is a chain of joins and filters:** grid × flights → CPA per (point, flight) → self-join
  for the 920 s offset → speed and distance filters → anti-join for silence. Script names like
  `1.1 v8 CRS fix`, `1.1b v2 aggregate`, `1.2a v9`, `1.2a v10`, and `remove jets from ca…` are the
  stages.

## Functionality worth adding to your kit

| Need | Polars | Why |
|---|---|---|
| Look at a file without loading it | `pl.scan_parquet(p).collect_schema()`, `.head().collect()` | Metadata only; instant on 50 GB |
| "What is in here?" | `df.describe()`, `df.null_count()`, `df.glimpse()`, `s.value_counts(sort=True)`, `s.n_unique()` | Your first five commands on any table |
| Nested data | `explode`, `unnest`, `pl.col(l).list.len()`, `.list.eval(...)`, `.struct.field(...)` | ADS-B traces, JSON APIs |
| Bigger than RAM | `scan_parquet(...).filter(...).collect(engine="streaming")`, `sink_parquet` | Predicate and projection pushdown read only what's needed |
| Per-group window math | `pl.col("t").diff().over("flightid")` | Reporting gaps, speeds from positions, without a groupby/merge dance |
| Time-binning | `group_by_dynamic("t", every="10m")`, `rolling(...)` | Traffic density per time slot (the silence question) |
| Nearest-in-time match | `join_asof(on="t", by="flightid", tolerance=…)` | Snap events to the closest track report |
| Interval/inequality joins | `join_where(other, pl.col("t2") - pl.col("t1") > 910, ...)` | The 920 s offset filter without materializing all pairs |
| Anti/semi joins | `how="anti"` / `how="semi"` | "Remove known jets", "drop points that heard anything in between" |
| SQL when you want it | `pl.SQLContext`, `df.sql("SELECT ...")` | Mix and match |

### DuckDB: the same thing from a shell, no Python, no IDE

DuckDB (<https://duckdb.org>) is a single binary that queries Parquet/CSV/JSON in place. Every query
below has been run against the synthetic data.

```sql
-- duckdb   (then paste; or: duckdb -c "...")
DESCRIBE SELECT * FROM 'data/flights.parquet';                 -- schema incl. nested STRUCT[]
SUMMARIZE SELECT flightid, type_code FROM 'data/flights.parquet';  -- min/max/uniques/nulls/quantiles
SELECT type_code, count(*) n FROM 'data/flights.parquet' GROUP BY ALL ORDER BY n DESC;
CREATE TABLE pts AS
  SELECT flightid, type_code, UNNEST(flight_trail_list, recursive := true) FROM 'data/flights.parquet';
SELECT count(*) FROM (SELECT flightid, timestamp FROM pts GROUP BY ALL HAVING count(*) > 1);  -- duplicates
SELECT p.type_code, count(DISTINCT flightid) n
FROM pts p ANTI JOIN read_csv('data/aircraft_types.csv') t
  ON p.type_code = t.type_designator AND t.engine_type = 'Jet'
GROUP BY ALL ORDER BY n DESC;                                  -- "remove known jets"
```

Also useful: the `spatial` extension (`INSTALL spatial; LOAD spatial;`) for `ST_Point`/`ST_Distance`
and for writing GeoPackage directly (`COPY … TO 'x.gpkg' WITH (FORMAT GDAL, DRIVER 'GPKG')`), and
`duckdb -ui` for a local notebook-style browser UI.

**When to use which:** DuckDB for "what's in this file?" and one-off aggregations from a terminal.
Polars once the logic involves loops, NumPy, or multi-step pipelines. Both read the same Parquet,
so switching costs nothing.

## Existing tutorials

- **[Polars user guide](https://docs.pola.rs/user-guide/)**: read *Concepts → Expressions*,
  *Lazy API*, *Joins* (including asof and `join_where`), and *Lists and Arrays / Structs*.
- **[Modern Polars](https://kevinheavey.github.io/modern-polars/)**: a side-by-side pandas → Polars
  translation through real data-cleaning tasks.
- **[DuckDB docs](https://duckdb.org/docs/)**: the `SUMMARIZE`, `UNNEST`, and "Friendly SQL" pages.
- For real ADS-B trace JSON (adsb.lol / readsb), the field layout is documented in readsb's
  `README-json.md` (<https://github.com/wiedehopf/readsb>).

## Tutorial: rebuild his funnel, `tutorials/polars_funnel.py`

```sh
uv run tutorials/make_dataset.py --out data
uv run tutorials/polars_funnel.py data
```

It's a `# %%`-cell script, so you can run it whole or cell by cell. Each cell opens with a question.
What it does, with the output I got:

| Cell | Question | Polars idea | Result |
|---|---|---|---|
| 1 | What is this file? | `scan_parquet`, `collect_schema`, `null_count`, `value_counts` | nested `list[struct]`, nulls in `type_code` |
| 2 | Flatten, and is it clean? | `explode` + `unnest`; `group_by().len()`; `diff().over()` | ~14k duplicate reports; mixed 1/2/5 s cadence |
| 3 | Props only? | **anti-join** against known jets (the lookup has gaps, as Doc 8643 does for him) | 262 → 188 flights |
| 4 | Metres, not degrees | equirectangular local frame | — |
| 5–6 | When would each grid point hear each flight? | per-flight **cross join** with the grid, `group_by(gid).agg(pl.all().sort_by("r").first())` → delayed CPA = t + r/c | 1.78M hearings, ~50 s |
| 7 | Heard a prop, then another ~920 s later? | **self-join on gid** + filter on `dt` | 14,491 grid points |
| 8 | Right speed and slant distance (from the Doppler fit)? | `is_between` on both events | 89 |
| 9 | Silence between the events? | join every hearing, keep those between the two times within range → **anti-join** | 31 points, 6 flight pairs |
| 11 | Hand off to QGIS | GeoPackage, one layer per stage | → [qgis.md](qgis.md) |

The surviving cluster includes the true location. `score_candidates.py` then separates the 6 pairs
with Doppler curve shape: the true pair wins, and the fine-grid best point is about 23 m from truth.

### Exercises, ordered by how much they build the "unknown schema" muscle

1. **Before reading cell 1**, write down what you think `flights.parquet` contains. Then run only
   `DESCRIBE` / `collect_schema()`. What surprised you?
2. Find the **unknown type codes** (cell 3 prints them). Look them up in
   [ICAO Doc 8643](https://www.icao.int/doc-8643-aircraft-type-designators-0) and decide whether removing only
   known jets was the right call.
3. Replace the self-join in cell 7 with `join_where` and compare memory use.
4. Replace the per-flight Python loop in cell 6 with a **tile join**: bin points and grid into 10 km
   tiles, join on neighboring tiles, then compute ranges. When is it faster than brute force?
5. Rewrite cells 1–3 in DuckDB SQL from a terminal.
6. **Real data.** Download one day of [adsb.lol history](https://www.adsb.lol/docs/open-data/historical/)
   (warning: it's large; extract only part of it). Don't read any docs first. Use
   `pl.read_json` / `duckdb` on one trace file and work out what each field is. Then check yourself
   against readsb's README-json.md. That's the closest you'll get to his first day with the FR24
   export.
