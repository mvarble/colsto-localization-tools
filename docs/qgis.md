# QGIS

**What it is:** QGIS is a free, open-source desktop GIS. It loads vector layers (points, lines,
polygons) and rasters (DEMs, imagery) and styles them by attribute. It also has a large toolbox of
spatial algorithms. It runs natively on Linux; distro packages and Flatpak are listed on the
[download page](https://qgis.org/download/). It's a GUI application in its own right, so no IDE is
involved.

- Site: <https://qgis.org>
- Docs: <https://docs.qgis.org/latest/en/docs/user_manual/>

Seen at 1:01, 3:20, 4:11, 4:26, 10:46, 11:29, 22:38, 25:00.

![QGIS at 1:01](../frames/1_01.jpg)

## How he uses it

QGIS is the map side of his loop. He never builds a map application. Python writes files, QGIS
displays them, he looks, and the next filter comes from what he saw.

1. **The layer tree works as a lab notebook** (1:01, 4:26, 22:38). His layers include `dem_mosaic`,
   `all_flight_paths`, and `prop_flight_paths`. There are groups named `single ev`, `post offset`,
   `post silence + of…`, `test area`, `flightpaths`, `event scores`, and `data error`, plus two
   groups called `old`, plus `th` and `misc`. Every funnel stage gets its own layer, so toggling a
   checkbox shows what a filter removed. The `old` groups are kept rather than deleted, so earlier
   hypotheses stay around for comparison.
2. **Every candidate goes on satellite basemaps** (`google`, `carto`, `bing` XYZ tile layers). This is
   how he spotted, at 11:00, that most of the 73,000 surviving points were **airports**. That
   observation became the "silence" filter. A good exploratory question comes from looking at
   survivors against real-world context.
3. **He uses the Identify tool on individual features** (4:26). Clicking a track point opens
   *Identify Results* with the raw row: `timestamp`, `utc_time`, `lat`, `lon`, `alt_ft`, `gs_kt`,
   `vs_fpm`, `track_deg`, `valid`. The layer is named `flight_1099966250_track_1sec`, so each flight
   was exported as its own layer when he needed to look at it closely.
4. **Graduated symbology on dense point grids** (1:01). The 200 m grid points are colored red to
   green by a score or time attribute. At 22:38 a 100 m fine-score grid with a rainbow ramp looks
   like a heat map. He doesn't rasterize anything; dense points plus a color ramp are enough.
5. **GeoPackage is the hand-off format.** His script list includes `flights to GPKG points.py` and
   `flight ID to gpkg do…`.
6. **The last step leaves GIS** (25:00). He copies the best coordinate and opens it in Google Maps
   Street View to match the treeline.

## Functionality worth adding to your kit

These go beyond what the frames show.

| Feature | Where | Why it matters for this kind of problem |
|---|---|---|
| **Temporal Controller** | View → Panels → Temporal Controller; per-layer *Properties → Temporal* | Scrubs tracks through time. "Was anything overhead between event 1 and event 2?" becomes something you watch. |
| **Filter / Query Builder** | Layer → right-click → *Filter…* | `"flightid" IN (…)` or `"r" < 2000` with no code and no new file. Fastest way to test a hypothesis. |
| **Select by Expression, Field Calculator** | Attribute table toolbar | Ad-hoc derived columns, e.g. `abs("dt" - 920)`, `"r_2" / "r"`. |
| **Virtual Layers (SQL)** | Layer → Add Layer → Add/Edit Virtual Layer | SQL across loaded layers, including joins between layers from different files. |
| **Heatmap renderer / KDE** | Symbology → *Heatmap*; Processing → *Heatmap (Kernel Density Estimation)* | Shows instantly where survivors pile up (airports!). |
| **Sample raster values** | Processing toolbox | Gives each grid point the DEM elevation under it, i.e. the slant-distance step from 6:00 in the video. |
| **Points to path** | Processing toolbox | Turns ADS-B points into one line per flight (group by `flightid`, order by `timestamp`). |
| **Elevation profile** | View → Elevation Profile (3.26+) | Terrain along a line. For RF, a quick line-of-sight check between antenna and target. |
| **Python console / `qgis_process`** | Plugins → Python Console; `qgis_process` CLI | Script repetitive styling, or run Processing algorithms headless from a shell. |
| **Lat Lon Tools plugin** | Plugin manager | Copy a coordinate or open it in an external map in one click (his final Street View step). |
| **QuickMapServices plugin** | Plugin manager | One-click basemaps instead of configuring XYZ URLs by hand. |

**Notes for RF work (L/S/X-band):** QGIS handles DEM-based viewshed and line-of-sight via the
*Visibility Analysis* plugin. You can also plot satellite ground tracks (generate points with skyfield
and load them as CSV) and style receiver detections by SNR. It's the same workflow as his with a
different signal.

## Existing tutorials worth your time

- **[QGIS Training Manual](https://docs.qgis.org/latest/en/docs/training_manual/)**: the official
  course. Skim the vector, attribute-table, and raster chapters and skip the rest.
- **[QGIS Tutorials and Tips](https://www.qgistutorials.com/)** by Ujaval Gandhi: short, task-shaped
  tutorials. Do these: *Working with Attributes*, *Basic Vector Styling*, *Importing Spreadsheets or
  CSV files*, *Performing Table Joins*, *Running Processing Algorithms via Python*.
- **[Spatiotemporal data exploration with QGIS](https://cartogis.readthedocs.io/en/latest/notebooks/week4/Spatiotemporal-anim-QGIS.html)**
  (CARTOGIS): the best walkthrough of the Temporal Controller with point data.

Those cover the mechanics. The tutorial below covers the habit of looking at survivors in context.

## Tutorial: the funnel on a map

Prerequisites (from the repo root):

```sh
uv run tutorials/make_dataset.py --out data
uv run tutorials/polars_funnel.py data       # writes data/funnel/funnel.gpkg
uv run tutorials/score_candidates.py data    # writes data/funnel/fine.gpkg
```

### 1. Basemap

In the Browser panel, right-click **XYZ Tiles → New Connection**. For Esri World Imagery, use
`https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}`.
OpenStreetMap is built in. Alternatively, install QuickMapServices.

### 2. Load the funnel

Drag `data/funnel/funnel.gpkg` onto the map. You'll get `stage1_offset`, `stage2_speed_dist`,
`stage3_silence`, and `track_points`. Put the three stage layers in a group named `funnel` and order
them stage 1 at the bottom, stage 3 on top.

### 3. Look before you filter

1. Style `stage1_offset` with **Heatmap** symbology. Where do the "heard a prop, then another one
   920 s later" points concentrate? Find the airport without being told where it is.
2. Toggle `stage2_speed_dist`. The points left near the airport are the false positives the silence
   filter exists to kill. Toggle `stage3_silence` and check that it does.

### 4. Inspect individual candidates

1. Use the Identify tool on a `stage3_silence` point and note its `flightid` / `flightid_2`.
2. On `track_points`, open **Filter…** and enter `"flightid" IN (<id1>, <id2>)`. These are the two
   flights that candidate supposedly heard.

### 5. Watch time

1. Open `track_points` → Properties → **Temporal**. Set Configuration to *Single field with
   date/time* and the field to `utc`.
2. Open the Temporal Controller, switch to animated mode, set the step to 10 s, and play across the
   recording window. Check that nothing passes near the candidate between the two events.
3. Find the recording window yourself. It's bracketed by the two flights' delayed-CPA times.

### 6. Fine scores as a heat map (the 22:38 view)

1. Load `data/funnel/fine.gpkg`, which holds 50 m points scored by curve fit.
2. Style it **Graduated** on `total` with the *Turbo* or *Spectral* ramp, 10 classes, Jenks breaks.
   The hot ridge is elongated because slant distance constrains position more than direction does.
   Think about why it's elongated along one axis.
3. Copy the hottest point's coordinate (Lat Lon Tools, or right-click → Copy Coordinate). Compare it
   with `data/TRUTH.json`. In my run the error was about 23 m.

### 7. Expressions instead of scripts

- **Select by Expression** on `stage1_offset`: `abs("dt" - 920) < 2 AND "r" < 3000`. How many points
  survive if your offset measurement was ±2 s instead of ±8 s?
- **Virtual layer** to count candidate points per flight pair:
  `SELECT flightid, flightid_2, count(*) AS n FROM stage2_speed_dist GROUP BY 1, 2 ORDER BY n DESC`.
- **Processing → Points to path** on `track_points`, grouped by `flightid` and ordered by
  `timestamp`, gives clean flight lines.

### 8. Stretch: a real DEM

The synthetic ground is flat at 350 m. Download a real DEM for an area you know (Copernicus GLO-30,
or USGS 3DEP in the US via OpenTopography). Lay a grid with *Create Grid* plus *Extract vertices*,
then run **Sample raster values**. Re-derive slant distances with the Field Calculator using an
aircraft altitude above *sea level*. How large is the error if you ignore terrain in hilly country?
