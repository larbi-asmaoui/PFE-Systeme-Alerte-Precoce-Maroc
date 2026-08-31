# ingestion_3 — station-based ingestion (NASA POWER + Z500/T850)

Batch ingestion of the per-station training dataset used by the temporal models
(`temporal_training/lstm_nasa_power.ipynb`). It collects two sources and merges
them per station, per day:

| Source | What | Producer | Raw output |
|---|---|---|---|
| **NASA POWER** (LARC) | daily surface meteo (Tmax/Tmin/RH/wind/pressure/solar/precip) + derived HeatIndex/WindChill | `nasa_power_producer.py` | `data/raw/nasa_power/<station>.csv` |
| **NOAA NCEP reanalysis** (PSL) | daily Z500 (geopotential) & T850 (850 hPa temp) — synoptic predictors | `upperair_producer.py` | `data/raw/upperair/<station>_upperair.csv` |

The **processor** joins them into the model-ready dataset:

```
station_processor.py → data/processed/stations/<station>.csv
                     → data/processed/stations_merged.parquet   (combined)
```

## Why Kafka for a *batch* pipeline?

We do **not** stream the climate payloads through Kafka — that would be the wrong
tool for a historical backfill. Instead Kafka is used exactly as it already is in
this repo (`gfs_producer.py`, `era5land_producer.py`): as an **optional manifest /
job bus**.

- Each producer downloads raw files to disk, then publishes one small **JSON
  manifest** per file (path, station, rows, date range) to a topic
  (`nasa-power-raw`, `upperair-raw`).
- The processor either **discovers files on disk** (`--no-kafka`, default for a
  one-shot backfill) or **consumes the manifests** (`--from-kafka`) to know what
  to merge — decoupling ingestion from processing with replay / at-least-once.

So: **one-shot historical backfill → `--no-kafka`**; **recurring daily
increments where you want decoupling/replay → Kafka on**. The heavy data stays on
disk / object storage; Kafka only carries lightweight events.

## Usage

```bash
pip install -r requirements.txt

# 1) Surface (full history, pure batch)
python nasa_power_producer.py --start 2000-01-01 --end 2025-12-31 --no-kafka

# 2) Upper-air (per-year NetCDF, pure batch)
python upperair_producer.py --start-year 1990 --end-year 2025 --no-kafka

# 3) Merge -> training-ready station dataset
python station_processor.py --no-kafka

# Recurring increment with the manifest bus (needs a Kafka broker on $KAFKA_BROKER)
python nasa_power_producer.py --days 30
python upperair_producer.py --start-year 2025 --end-year 2025
python station_processor.py --from-kafka
```

### Environment
`KAFKA_BROKER` (default `localhost:9092`), `KAFKA_TOPIC_NASA`
(`nasa-power-raw`), `KAFKA_TOPIC_UPPERAIR` (`upperair-raw`), `KAFKA_GROUP`.

## Daily forecast pipeline (nowcast → spatialization → dashboard)

Once a model is trained (`temporal_training/` → `artifacts/`), the *daily* job does
**not** re-download history. It ingests only the recent window, predicts, turns the
30 station forecasts into a national risk surface, and feeds the 2D dashboard:

```
            ┌ Stage 0 (optional daily increment) ──────────────────────────┐
            │ nasa_power_producer.py --days 14   (+ upperair if model uses) │
            └──────────────────────────────────────────────────────────────┘
                                   │
┌ Stage 1 — predict_stations.py (TensorFlow, lightweight, NO Spark) ────────┐
│ best .keras + scaler_X/scaler_y + lstm_meta.json                          │
│ last `input_window` days per station -> next `output_window` days         │
│ -> data/processed/station_forecasts.geojson  (30 Point features)          │
└───────────────────────────────────────────────────────────────────────────┘
                                   │
┌ Stage 2 — spark_sedona_spatial.py (Apache Spark + Apache Sedona) ──────────┐
│ ST_H3CellIDs  -> hex grid over Morocco, clipped with ST_Intersects        │
│ ST_DistanceSphere k-NN + IDW (1/dᵖ) interpolation of the 7-day forecast   │
│ severity/alert per hex per day                                            │
│ -> public/data/today_alerts.geojson  (Polygon hex choropleth)             │
└───────────────────────────────────────────────────────────────────────────┘
                                   │
┌ Stage 3 — dashboard (src/components/map/HeatMap.tsx) ─────────────────────┐
│ deck.gl GeoJsonLayer: borderless H3 choropleth, continuous severity ramp  │
│ (smooth gradient field), day slider, 2D (pitch 0).                        │
└───────────────────────────────────────────────────────────────────────────┘
```

> **Forecast date / season.** The forecast covers the 7 days *after the input
> window's last row*. The merged training data currently ends `2025-12-31`, so the
> default run forecasts Jan 2026 (a winter cold-wave). Pass `--base-date` (or the
> 3rd arg to `run_nowcast.sh`) to issue the forecast as-of any historical date —
> e.g. `--base-date 2025-06-27` gives a seasonally-correct *summer heat* forecast
> for late June. Once live daily ingestion (Stage 0) is wired, the default run is
> the true current week.

Run the whole thing:

```bash
./run_nowcast.sh                          # last available data (winter → Jan 2026)
./run_nowcast.sh 6 6 2025-06-27           # summer heat demo for late June
# or manually:
python predict_stations.py --base-date 2025-06-27
python spark_sedona_spatial.py --h3-res 6 --k 6 --power 2
```

The dashboard colours every hexagon on a **continuous severity ramp** (not 4
discrete buckets) with borderless fills, so the H3 grid reads as a smooth WPC-style
field. The per-hex payload is stored as **compact per-day arrays** (`hi/wc/sev/lvl`)
with the dates once at collection level — a res-6 file is ~9 MB instead of ~24 MB.

**Why Spark/Sedona here is justified:** the cost scales with the *resolution* of the
interpolated surface (res 5 ≈ 2,800 hexes, **res 6 ≈ 18,800**, res 7 ≈ 10⁵–10⁶) × 7
days × the k-NN spatial join — not with the 30 stations. The model inference
(Stage 1) stays a lightweight single-process TF job; Spark starts only at the
spatialization stage. Default is `--h3-res 6` (~9 MB, smooth); `--h3-res 5`
(~3.6 MB) is the lighter option.

**Serving:** Stage 2 writes the GeoJSON the dashboard reads directly
(`public/data/today_alerts.geojson`). For production scale, load the polygons into
**PostGIS** (GIST index) and serve MVT vector tiles via the existing `pg_tileserv`
service — the GeoJSON path is the no-infra default used for local runs.

## Layout
```
ingestion_3/
  stations.py             # single source of truth: 30 stations + geo helpers
  features.py             # HeatIndex / WindChill (matches nasa_power_data.py)
  kafka_bus.py            # optional manifest producer (no-op with --no-kafka)
  nasa_power_producer.py  # surface producer
  upperair_producer.py    # Z500/T850 producer
  station_processor.py    # merge surface + upper-air -> model-ready dataset
  predict_stations.py     # Stage 1: TF nowcast (last 7 -> next 7 days)
  spark_sedona_spatial.py # Stage 2: Spark + Sedona H3/IDW risk surface
  run_nowcast.sh          # Stage 1 + Stage 2 runner
  requirements.txt
```
