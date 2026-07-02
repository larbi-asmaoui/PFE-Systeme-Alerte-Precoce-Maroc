#!/usr/bin/env bash
# Daily nowcast pipeline: station forecast (TF) -> Sedona spatial surface -> dashboard GeoJSON.
# Usage: ./run_nowcast.sh [H3_RES] [K] [BASE_DATE]
#   BASE_DATE (YYYY-MM-DD, optional): issue the forecast as-of this date. Omit to
#   use the last available row. Use a summer date for a seasonally-correct heat
#   demo until live daily ingestion is wired (data currently ends 2025-12-31).
set -euo pipefail
cd "$(dirname "$0")"

H3_RES="${1:-6}"   # 6 ≈ 18.8k hexes (~9 MB, smooth field); 5 ≈ 2.8k (lighter)
K="${2:-6}"
BASE_DATE="${3:-}"

echo "==> Stage 1: station nowcast (TensorFlow)"
if [[ -n "${BASE_DATE}" ]]; then
  python3 predict_stations.py --base-date "${BASE_DATE}"
else
  python3 predict_stations.py
fi

echo "==> Stage 2: Sedona spatialization (H3 res ${H3_RES}, k=${K})"
python3 spark_sedona_spatial.py --h3-res "${H3_RES}" --k "${K}" --power 2

echo "==> Done. Dashboard reads public/data/today_alerts.geojson"
