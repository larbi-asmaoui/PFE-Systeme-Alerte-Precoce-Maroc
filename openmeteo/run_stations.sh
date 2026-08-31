#!/usr/bin/env bash
# SAP Morocco — Pipeline A (stations) daily nowcast.
#   Stage 0: ingest last 7 days from Open-Meteo -> data/live/openmeteo/*_cleaned.csv (+ MinIO)
#   Stage 1: GRU predict last7 -> next7 -> public/data/stations_forecast.geojson
#
# Usage:  ./openmeteo/run_stations.sh [DAYS]
set -euo pipefail
cd "$(dirname "$0")/.."

DAYS="${1:-7}"

echo ">> Stage 0 — Open-Meteo ingestion (${DAYS} days)"
python3 openmeteo/openmeteo_producer.py --days "${DAYS}"

echo ">> Stage 1 — GRU station forecast"
python3 backend/predict_stations.py \
    --stations data/live/openmeteo \
    --out public/data/stations_forecast.geojson

echo ">> Done. Dashboard reads public/data/stations_forecast.geojson (GET /api/v1/alerts/stations)"
