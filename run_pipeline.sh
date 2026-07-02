#!/usr/bin/env bash
# ===========================================================================
# SAP Morocco — sequential batch pipeline (replaces Airflow/Kafka).
#
# Runs the four stages end-to-end and produces public/data/today_alerts.geojson
# with REAL predictions masked to Morocco's land borders:
#
#   1. era5land_producer.py   download 7 days of ERA5-Land NetCDF from CDS
#   2. era5land_processor.py  -> normalized [7, 13, 37, 65] tensor
#   3. predictor.py           convlstm_best.pt -> [7, 2, 37, 65] prediction
#   4. spark_spatial_batch.py Sedona ocean mask -> today_alerts.geojson
#
# Intended to run inside the batch runner container (has Java/Spark + all deps):
#   docker compose run --rm spark_processor bash run_pipeline.sh
#
# Env knobs:
#   START, END      override the 7-day window (YYYY-MM-DD)
#   LATENCY         ERA5-Land latency in days (default 5)
#   PIP_INSTALL=0   skip dependency install (e.g. on a warm/persistent container)
#   USE_MINIO=1     archive the raw prediction to MinIO too (needed for /alerts/point)
#   MOROCCO_SHAPEFILE  boundary file for the ocean mask
# ===========================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

LATENCY="${LATENCY:-5}"
END="${END:-$(date -u -d "${LATENCY} days ago" +%F)}"
START="${START:-$(date -u -d "$((LATENCY + 6)) days ago" +%F)}"
SHAPEFILE="${MOROCCO_SHAPEFILE:-$ROOT/data/shapefiles/morocco/morocco.geojson}"

echo "=================================================================="
echo " SAP batch pipeline | window: $START -> $END"
echo " repo: $ROOT | shapefile: $SHAPEFILE"
echo "=================================================================="

# ---- 0. dependencies (skip with PIP_INSTALL=0 on a warm container) ----------
if [ "${PIP_INSTALL:-1}" = "1" ]; then
  echo "[deps] installing python dependencies (first run is slow)..."
  pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
  pip install --no-cache-dir \
    cdsapi xarray netCDF4 h5netcdf numpy \
    apache-sedona geopandas shapely \
    boto3 psycopg2-binary
fi

# ---- 1. ERA5-Land download -------------------------------------------------
echo "[1/4] ERA5-Land download ($START -> $END)"
python ingestion_2/era5land_producer.py --start "$START" --end "$END"

# ---- 2. Build 13-channel tensor --------------------------------------------
echo "[2/4] Build normalized [7,13,37,65] tensor"
python ingestion_2/era5land_processor.py --start "$START" --end "$END"

TENSOR="$(ls -t "$ROOT"/data/ready_for_inference/tensor_live_*.npy 2>/dev/null | head -1 || true)"
[ -n "$TENSOR" ] || { echo "ERROR: no tensor_live_*.npy produced"; exit 1; }
echo "      tensor: $TENSOR"

# ---- 3. PyTorch inference --------------------------------------------------
echo "[3/4] PyTorch inference (convlstm_best.pt)"
MINIO_FLAG="--no-minio"
[ "${USE_MINIO:-0}" = "1" ] && MINIO_FLAG=""
( cd "$ROOT/backend" && python predictor.py --file "$TENSOR" $MINIO_FLAG )

PRED="$(ls -t "$ROOT"/data/ready_for_inference/raw_pred_*.npy 2>/dev/null | head -1 || true)"
[ -n "$PRED" ] || { echo "ERROR: no raw_pred_*.npy produced"; exit 1; }
echo "      prediction: $PRED"

# ---- 4. Sedona ocean mask -> today_alerts.geojson --------------------------
echo "[4/4] Sedona ocean mask -> today_alerts.geojson"
python ingestion/spark_spatial_batch.py \
  --pred "$PRED" \
  --shapefile "$SHAPEFILE" \
  --out "$ROOT/public/data/today_alerts.geojson"

echo "=================================================================="
echo " DONE -> public/data/today_alerts.geojson"
echo " Open http://localhost:3000 to view the real predictions."
echo "=================================================================="
