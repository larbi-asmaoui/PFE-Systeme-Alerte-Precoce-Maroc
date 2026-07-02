"""
Sedona batch step: ocean-mask the prediction grid and emit today_alerts.geojson.

Final stage of the batch pipeline. Takes the raw model prediction tensor
[7, 2, 37, 65] (channels: 0=HeatIndex, 1=WindChill) produced by predictor.py,
keeps only the grid cells that fall on Moroccan land (distributed Spatial SQL via
Apache Sedona, ``ST_Intersects``), and writes the GeoJSON grid the Deck.gl
frontend consumes — one Polygon feature per land cell with a 7-day forecast.

Output schema (matches src/components/map/HeatMap.tsx):
    Feature.properties = {
        row, col, lat, lon,
        alert_level, severity,            # worst day in the window
        forecasts: [                      # one per forecast day
            {day, date, heat_index, wind_chill, severity, alert_level}, ...
        ]
    }

Run inside the batch runner container (provides Spark + the Sedona jars via
PYSPARK_SUBMIT_ARGS):

    python ingestion/spark_spatial_batch.py \
        --pred  data/ready_for_inference/raw_pred_YYYYMMDD.npy \
        --shapefile $MOROCCO_SHAPEFILE \
        --out   public/data/today_alerts.geojson

Environment:
    MOROCCO_SHAPEFILE  boundary file (.shp or .geojson; read with geopandas).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Paths & model grid — keep in sync with backend/app/core/meteo.py
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
READY_DIR = PROJECT_ROOT / "data" / "ready_for_inference"
DEFAULT_OUT = PROJECT_ROOT / "public" / "data" / "today_alerts.geojson"

GRID_LAT_NORTH = 36.0
GRID_LAT_SOUTH = 27.0
GRID_LON_WEST = -17.0
GRID_LON_EAST = -1.0
GRID_ROWS = 37
GRID_COLS = 65
FORECAST_HORIZON = 7

GRID_LATS = np.linspace(GRID_LAT_NORTH, GRID_LAT_SOUTH, GRID_ROWS)
GRID_LONS = np.linspace(GRID_LON_WEST, GRID_LON_EAST, GRID_COLS)

CH_HEAT_INDEX = 0
CH_WIND_CHILL = 1

# Alert thresholds — mirror backend/app/core/meteo.py (felt_severity + mapping).
HEAT_INDEX_ALERT_BASELINE_C = 32.0
WIND_CHILL_ALERT_BASELINE_C = 5.0


def felt_severity(heat_index: float, wind_chill: float) -> float:
    heat = heat_index - HEAT_INDEX_ALERT_BASELINE_C
    cold = WIND_CHILL_ALERT_BASELINE_C - wind_chill
    return max(heat, cold)


def severity_to_alert_level(severity: float) -> str:
    if severity <= 0.0:
        return "none"
    if severity > 5.0:
        return "red"
    if severity > 2.0:
        return "orange"
    return "yellow"


def _cell_polygon(row: int, col: int) -> list[list[list[float]]]:
    """[lon, lat] ring for the 0.25° grid cell at (row, col)."""
    dlat = (GRID_LAT_NORTH - GRID_LAT_SOUTH) / (2 * GRID_ROWS)
    dlon = (GRID_LON_EAST - GRID_LON_WEST) / (2 * GRID_COLS)
    lat, lon = float(GRID_LATS[row]), float(GRID_LONS[col])
    return [[
        [lon - dlon, lat - dlat],
        [lon + dlon, lat - dlat],
        [lon + dlon, lat + dlat],
        [lon - dlon, lat + dlat],
        [lon - dlon, lat - dlat],
    ]]


def _latest_pred() -> str:
    files = sorted(glob.glob(str(READY_DIR / "raw_pred_*.npy")))
    if not files:
        raise FileNotFoundError(
            f"No raw_pred_*.npy in {READY_DIR} — run predictor.py first"
        )
    return files[-1]


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sedona ocean-mask -> today_alerts.geojson")
    p.add_argument("--pred", default=None, help="Prediction tensor [7,2,37,65] (default: latest)")
    p.add_argument(
        "--shapefile",
        default=os.getenv("MOROCCO_SHAPEFILE", str(PROJECT_ROOT / "data" / "shapefiles" / "morocco" / "morocco.geojson")),
        help="Morocco boundary (.shp or .geojson)",
    )
    p.add_argument("--out", default=str(DEFAULT_OUT), help="Output GeoJSON path")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    pred_path = args.pred or _latest_pred()

    pred = np.load(pred_path).astype(np.float32)
    if pred.shape != (FORECAST_HORIZON, 2, GRID_ROWS, GRID_COLS):
        raise ValueError(
            f"Expected prediction shape (7, 2, 37, 65), got {pred.shape}"
        )

    if not Path(args.shapefile).exists():
        raise FileNotFoundError(
            f"Boundary file not found: {args.shapefile}. Set MOROCCO_SHAPEFILE "
            f"or pass --shapefile (a .shp or .geojson of Morocco)."
        )

    # --- Lazy imports so the file is inspectable without Spark installed ---
    import geopandas as gpd
    from sedona.spark import SedonaContext
    from pyspark.sql import functions as F
    from pyspark.sql.types import StructType, StructField, IntegerType, DoubleType

    config = SedonaContext.builder().appName("sap-ocean-mask").getOrCreate()
    sedona = SedonaContext.create(config)
    sc = sedona.sparkContext

    # 1. Every grid cell -> Spark DataFrame with a point geometry
    rows = [
        (r, c, float(GRID_LATS[r]), float(GRID_LONS[c]))
        for r in range(GRID_ROWS)
        for c in range(GRID_COLS)
    ]
    schema = StructType([
        StructField("row", IntegerType(), False),
        StructField("col", IntegerType(), False),
        StructField("lat", DoubleType(), False),
        StructField("lon", DoubleType(), False),
    ])
    cells = sedona.createDataFrame(rows, schema=schema)
    cells = cells.withColumn("geom", F.expr("ST_Point(lon, lat)"))
    cells.createOrReplaceTempView("cells")

    # 2. Morocco polygon (geopandas reads .shp or .geojson) -> Sedona view
    gdf = gpd.read_file(args.shapefile).to_crs(epsg=4326)
    morocco_wkt = sc.broadcast(gdf.geometry.union_all().wkt)
    morocco_df = sedona.createDataFrame([(morocco_wkt.value,)], ["wkt"])
    morocco_df = morocco_df.withColumn("geom", F.expr("ST_GeomFromText(wkt)"))
    morocco_df.createOrReplaceTempView("morocco")

    # 3. Distributed spatial filter: keep land cells only
    land = sedona.sql(
        """
        SELECT c.row, c.col, c.lat, c.lon
        FROM cells c, morocco m
        WHERE ST_Intersects(c.geom, m.geom)
        """
    )
    land_cells = [(r["row"], r["col"]) for r in land.collect()]
    print(f"[Sedona] land cells: {len(land_cells)}/{GRID_ROWS * GRID_COLS}")

    # 4. Build the GeoJSON grid (driver-side; the grid is tiny once masked)
    start_date = datetime.utcnow()
    features = []
    for r, c in land_cells:
        day_forecasts = []
        max_sev = -999.0
        for d in range(FORECAST_HORIZON):
            hi = float(pred[d, CH_HEAT_INDEX, r, c])
            wc = float(pred[d, CH_WIND_CHILL, r, c])
            sev = felt_severity(hi, wc)
            max_sev = max(max_sev, sev)
            day_forecasts.append({
                "day": d,
                "date": (start_date + timedelta(days=d)).strftime("%Y-%m-%d"),
                "heat_index": round(hi, 1),
                "wind_chill": round(wc, 1),
                "severity": round(max(0.0, sev), 1),
                "alert_level": severity_to_alert_level(sev),
            })
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": _cell_polygon(r, c)},
            "properties": {
                "row": int(r),
                "col": int(c),
                "lat": round(float(GRID_LATS[r]), 4),
                "lon": round(float(GRID_LONS[c]), 4),
                "alert_level": severity_to_alert_level(max_sev),
                "severity": round(max(0.0, max_sev), 1),
                "forecasts": day_forecasts,
            },
        })

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": features}, fh)
    print(f"[Sedona] wrote {len(features)} land features -> {out_path}")

    sedona.stop()


if __name__ == "__main__":
    main()
