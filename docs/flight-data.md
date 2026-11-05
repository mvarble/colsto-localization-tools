# Flight data: Flightradar24 API + pyfr24 (and free alternatives)

This isn't an analysis tool, but you can't practice his workflow without the data, and its quirks
shaped his code.

![Sources at 3:03-3:20](../frames/3_03-3_20_sources.jpg)

## What he used

- **Flightradar24 API** (paid; the "B2B: Explore our flight data API" panel at 3:03). It provides
  historical tracks per flight ID. Portal: <https://fr24api.flightradar24.com>.
- **[`pyfr24`](https://github.com/stiles/pyfr24)** (3:07), a Python client and CLI for that API.
  It fetches flight tracks by ID, does a `smart-export` by flight number and date, and exports to
  CSV, GeoJSON, or KML. It needs an API subscription token (`FLIGHTRADAR_API_KEY`). Docs:
  <https://pyfr24.readthedocs.io>. He "ran this for a few hours to get all the flights in the
  continental US on September 8th."
- **ICAO Doc 8643 aircraft type designators** (4:03): <https://www.icao.int/doc-8643-aircraft-type-designators-0>.
  The *Engine Type* column (Jet / Piston / Turboprop …) let him drop jets. The table has gaps, so he
  *removed known jets* rather than *keeping known props*.
- **A DEM** (`download DEM.py`, layer `dem_mosaic_1…`). Altitude is above sea level, so slant
  distance needs ground elevation at every grid point (6:00). In the US the likely source is USGS
  3DEP (via The National Map or OpenTopography). Elsewhere, Copernicus GLO-30.

**Quirks visible in his code:** FR24 numeric flight IDs are **recycled** (3:12 docstring); a
`valid` flag on track points (4:26); full flight paths that leave the region (Hawaii, other
countries at 3:20).

## Free alternatives for practice (all usable from Linux)

| Source | What | Access |
|---|---|---|
| **adsb.lol** | Global community ADS-B, one GitHub release per day, gzip JSON per aircraft (readsb trace format), ODbL license | <https://www.adsb.lol/docs/open-data/historical/>, repos `adsblol/globe_history_20xx` |
| **OpenSky Network** | Research-grade historical ADS-B and Mode S in a Trino database | Free account; Python client [`pyopensky`](https://github.com/open-aviation/pyopensky) |
| **`traffic`** | Python toolbox for trajectories: resampling, filtering, airspace intersection, OpenSky access | <https://traffic-viz.github.io> |
| **Your own receiver** | RTL-SDR plus `readsb`/`dump1090` at **1090 MHz (L-band)** gives your own ADS-B ground truth | Any distro; `tar1090` for a web map |

## Capstone (your domain): run his whole experiment yourself

1. Put an RTL-SDR with a 1090 MHz antenna on a window and run `readsb` for a day, saving traces.
2. Leave a phone or USB mic recording outdoors (or at an open window) for an hour.
3. Find the prop flyovers in the audio ([audiolens.md](audiolens.md)), fit them
   (`tutorials/fit_trace.py`), and run the funnel ([polars.md](polars.md)) on *your* ADS-B data.
   Pretend you don't know where the mic was.
4. You have ground truth for both the receiver and the microphone location.

## The satellite version of the same problem

LEO satellite downlinks (VHF/UHF, plus L- and S-band) have Doppler curves just like planes, with
c = speed of light and much larger shifts.

- **[SatNOGS Network](https://network.satnogs.org)** publishes thousands of observations, each with a
  waterfall, audio, the station's location, and the satellite's TLE. The API is at
  `network.satnogs.org/api/observations/?format=json`; the audio is linked in the `archive_url`
  field. IQ files generally aren't published, so use the audio.
- Predict the Doppler curve with [skyfield](https://rhodesmill.org/skyfield/) from the TLE and the
  station location, and overlay it on the waterfall. That's a fork of `doppler_explorer.py` with a
  different model.
- **Then hide the station.** Grid-search candidate station locations by how well the predicted curve
  fits the recorded one. It's the video's method one band up, with known truth.
