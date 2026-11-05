# /// script
# requires-python = ">=3.11"
# dependencies = ["polars", "numpy", "pyarrow", "geopandas", "pyogrio", "shapely"]
# ///
"""
Polars tutorial: rebuild the video's candidate "funnel" on the synthetic dataset.

    uv run tutorials/make_dataset.py --out data        # once
    uv run tutorials/polars_funnel.py data             # whole thing, prints as it goes

Or open it cell-by-cell (`# %%` markers work in VS Code/PyCharm, `jupytext`, or paste into
`uv run --with polars ipython`). Each cell asks a question, then answers it with a few lines of
Polars. The questions are the point: in the video, each filter started as a "what if" that
got checked against the map.

Things you're expected to *measure yourself* from the audio first (doppler_explorer.py):
  AUDIO_OFFSET_S, EVENT{1,2}_SPEED_MS, EVENT{1,2}_SLANT_M. Defaults below are generous
  ranges around the truth so the script runs end to end.
"""
# %% ---------------------------------------------------------------- 0. setup
import math
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl

DATA = Path(sys.argv[1] if len(sys.argv) > 1 else "data")
OUT = DATA / "funnel"
OUT.mkdir(exist_ok=True)
pl.Config.set_tbl_rows(12).set_tbl_cols(12).set_fmt_str_lengths(40)

C = 343.0                      # m/s
GROUND_M = 350.0               # flat ground here; in real life: sample a DEM per grid point
AUDIO_OFFSET_S = 920.0         # measured between the two delayed-CPA moments in the audio
OFFSET_TOL_S = 8.0             # measurement slop, both events combined
EVENT1_SPEED_MS = (48, 66)     # from the Doppler fit (generous!)
EVENT2_SPEED_MS = (105, 130)
EVENT1_SLANT_M = (1300, 2600)
EVENT2_SLANT_M = (2600, 4500)
MAX_AUDIBLE_M = 10_000         # nothing beyond this is "heard"
GRID_M = 400.0


def step(msg):
    print(f"\n=== {msg}")


# %% ---------------------------------------------------------------- 1. what is this file?
# Never trust that you know the schema. Ask the file. scan_* is lazy: this reads only metadata.
step("1. schema discovery")
lf = pl.scan_parquet(DATA / "flights.parquet")
print(lf.collect_schema())
flights = lf.collect()
print(flights.head(3))
print("rows:", flights.height)
print(flights.null_count())
print(flights["type_code"].value_counts(sort=True).head(20))
# -> flight_trail_list is list[struct]. One row per flight, a nested list of reports inside.

# %% ---------------------------------------------------------------- 2. flatten
# explode: one row per list element. unnest: struct fields -> columns. (Same as the video's explode_trail.)
step("2. explode + unnest")
pts = (
    flights.select("flightid", "type_code", "flight_trail_list")
    .explode("flight_trail_list")
    .unnest("flight_trail_list")
)
print(pts.head())
print(pts.describe())
# Sanity questions worth asking any track table:
dups = pts.group_by("flightid", "timestamp").len().filter(pl.col("len") > 1)
print("duplicate (flightid, timestamp) rows:", dups.height)
gaps = (pts.sort("flightid", "timestamp")
        .with_columns(dt=pl.col("timestamp").diff().over("flightid"))
        .group_by("flightid").agg(pl.col("dt").median().alias("median_dt"), pl.col("dt").max().alias("max_dt")))
print(gaps["median_dt"].value_counts(sort=True))          # -> mixed 1 s / 2 s / 5 s reporting

pts = (pts.unique(["flightid", "timestamp"], keep="first")
          .drop_nulls("alt_ft")
          .sort("flightid", "timestamp"))

# %% ---------------------------------------------------------------- 3. prop planes only
# The lookup has gaps (like ICAO Doc 8643 vs real data). The video's trick: don't keep "known props",
# *remove known jets*. Unknown types survive. Anti-join does exactly that.
step("3. remove known jets")
types = pl.read_csv(DATA / "aircraft_types.csv")
jets = types.filter(pl.col("engine_type") == "Jet").select(pl.col("type_designator").alias("type_code"))
unknown = flights.join(types, left_on="type_code", right_on="type_designator", how="anti")
print("type codes with no lookup entry:", unknown["type_code"].unique().to_list())
props = pts.join(jets, on="type_code", how="anti")
print(f"{pts['flightid'].n_unique()} flights -> {props['flightid'].n_unique()} after removing known jets")

# %% ---------------------------------------------------------------- 4. metres, not degrees
# Equirectangular local frame around the data's centre. Good to ~0.1% over 60 km; for a country-wide
# search you'd use a proper projection (pyproj) or do this per tile.
step("4. project to a local metric frame")
lat0, lon0 = pts["lat"].mean(), pts["lon"].mean()
KX, KY = 111_320.0 * math.cos(math.radians(lat0)), 111_320.0


def to_xy(df):
    return df.with_columns(x=(pl.col("lon") - lon0) * KX, y=(pl.col("lat") - lat0) * KY,
                           z=pl.col("alt_ft") * 0.3048)


pts = to_xy(pts)
props = to_xy(props)

# %% ---------------------------------------------------------------- 5. the grid
step("5. lay a grid over the area")
# Only where prop traffic actually is (jets cross the whole state and would blow the grid up)
xmin, xmax, ymin, ymax = (props[c].quantile(q) for c, q in [("x", .05), ("x", .95), ("y", .05), ("y", .95)])
gx = np.arange(xmin, xmax, GRID_M)
gy = np.arange(ymin, ymax, GRID_M)
GX, GY = np.meshgrid(gx, gy)
grid = pl.DataFrame({"gx": GX.ravel(), "gy": GY.ravel()}).with_row_index("gid")
print(f"{grid.height:,} grid points ({gx.size} x {gy.size} @ {GRID_M:.0f} m)")

# %% ---------------------------------------------------------------- 6. CPA for every (grid point, flight)
# Brute force on purpose: cross join a flight's track with the grid, compute slant range, keep the
# minimum per grid point. ~10M rows per flight is nothing for Polars. "Quick and dirty" = brute force
# whenever brute force is affordable; get clever only when it isn't.
#
# delayed CPA time = time the plane was closest + time for that sound to reach the observer.
step("6. CPA + delayed CPA per (grid point, flight)  [all flights; silence filter needs jets too]")
t0 = time.time()
hear = []
track2s = pts.filter((pl.col("timestamp") % 2) == 0)       # thin to <=2 s; CPA time error <~1 s
for (fid,), trk in track2s.group_by(["flightid"]):
    bx = (trk["x"].min() - MAX_AUDIBLE_M, trk["x"].max() + MAX_AUDIBLE_M)
    by = (trk["y"].min() - MAX_AUDIBLE_M, trk["y"].max() + MAX_AUDIBLE_M)
    g = grid.filter(pl.col("gx").is_between(*bx) & pl.col("gy").is_between(*by))
    if g.is_empty():
        continue
    cpa = (
        g.join(trk.select("timestamp", "x", "y", "z", "gs_kt"), how="cross")
        .with_columns(r=((pl.col("x") - pl.col("gx")) ** 2 + (pl.col("y") - pl.col("gy")) ** 2
                         + (pl.col("z") - GROUND_M) ** 2).sqrt())
        .group_by("gid")
        .agg(pl.all().sort_by("r").first())                  # row of minimum slant range
        .filter(pl.col("r") < MAX_AUDIBLE_M)
        .select("gid", pl.lit(fid).alias("flightid"), "r",
                (pl.col("timestamp") + pl.col("r") / C).alias("t_dcpa"),
                (pl.col("gs_kt") * 0.514444).alias("gs_ms"))
    )
    hear.append(cpa)
hear = pl.concat(hear).join(flights.select("flightid", "type_code"), on="flightid")
print(f"{hear.height:,} (grid point, flight) hearings in {time.time() - t0:.1f}s")
hear.write_parquet(OUT / "hearings.parquet")

# %% ---------------------------------------------------------------- 7. the 920 s question
# "Somewhere that heard a prop, then ~920 s later heard another prop." Self-join per grid point.
step("7. time-offset filter")
ph = hear.join(jets, on="type_code", how="anti")
pairs = (
    ph.join(ph, on="gid", suffix="_2")
    .filter(pl.col("flightid") != pl.col("flightid_2"))
    .with_columns(dt=pl.col("t_dcpa_2") - pl.col("t_dcpa"))
    .filter((pl.col("dt") - AUDIO_OFFSET_S).abs() < OFFSET_TOL_S)
)
print(f"{pairs['gid'].n_unique():,} grid points survive ({pairs.height:,} flight pairs)")
pairs.join(grid, on="gid").write_csv(OUT / "stage1_offset.csv")

# %% ---------------------------------------------------------------- 8. speed and distance (from the Doppler fit)
step("8. velocity + slant-distance filter")
stage2 = pairs.filter(
    pl.col("gs_ms").is_between(*EVENT1_SPEED_MS) & pl.col("gs_ms_2").is_between(*EVENT2_SPEED_MS)
    & pl.col("r").is_between(*EVENT1_SLANT_M) & pl.col("r_2").is_between(*EVENT2_SLANT_M)
)
print(f"{stage2['gid'].n_unique():,} grid points survive")
stage2.join(grid, on="gid").write_csv(OUT / "stage2_speed_dist.csv")

# %% ---------------------------------------------------------------- 9. silence is a signal
# Disqualify any point that would have heard ANY flight (jets included) between the two events,
# at a range no farther than the farther of the two events (the conservative rule from the video).
step("9. silence filter")
between = (
    stage2.select("gid", "flightid", "flightid_2", "t_dcpa", "t_dcpa_2",
                  pl.max_horizontal("r", "r_2").alias("audible_m"))
    .join(hear.select("gid", pl.col("flightid").alias("other"), pl.col("t_dcpa").alias("t_other"),
                      pl.col("r").alias("r_other")), on="gid")
    .filter((pl.col("other") != pl.col("flightid")) & (pl.col("other") != pl.col("flightid_2"))
            & pl.col("t_other").is_between("t_dcpa", "t_dcpa_2")
            & (pl.col("r_other") <= pl.col("audible_m")))
    .select("gid", "flightid", "flightid_2").unique()
)
stage3 = stage2.join(between, on=["gid", "flightid", "flightid_2"], how="anti")
print(f"{stage3['gid'].n_unique():,} grid points survive")

# %% ---------------------------------------------------------------- 10. what's left, and where?
step("10. survivors, grouped by flight pair")
summary = (
    stage3.join(grid, on="gid")
    .group_by("flightid", "flightid_2")
    .agg(pl.len().alias("n_points"), pl.col("gx").mean(), pl.col("gy").mean(),
         pl.col("r").mean().alias("r1"), pl.col("r_2").mean().alias("r2"))
    .with_columns(lat=lat0 + pl.col("gy") / KY, lon=lon0 + pl.col("gx") / KX)
    .sort("n_points", descending=True)
)
print(summary)

# %% ---------------------------------------------------------------- 11. hand off to QGIS
# One GeoPackage, one layer per funnel stage -> in QGIS each becomes a toggleable layer, exactly like
# the "post offset / post silence" layers in his layer tree.
step("11. write GeoPackage for QGIS")
import geopandas as gpd


def to_gdf(df):
    df = df.with_columns(lat=lat0 + pl.col("gy") / KY, lon=lon0 + pl.col("gx") / KX).to_pandas()
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs="EPSG:4326")


gpkg = OUT / "funnel.gpkg"
gpkg.unlink(missing_ok=True)
for name, df in [("stage1_offset", pairs), ("stage2_speed_dist", stage2), ("stage3_silence", stage3)]:
    to_gdf(df.join(grid, on="gid")).to_file(gpkg, layer=name)
# Tracks as points with a real datetime, so QGIS's Temporal Controller can scrub them
trk = pts.with_columns(utc=pl.from_epoch("timestamp", time_unit="s")).to_pandas()
gpd.GeoDataFrame(trk, geometry=gpd.points_from_xy(trk.lon, trk.lat), crs="EPSG:4326").to_file(gpkg, layer="track_points")
print("wrote", gpkg, "layers: stage1_offset, stage2_speed_dist, stage3_silence, track_points")
