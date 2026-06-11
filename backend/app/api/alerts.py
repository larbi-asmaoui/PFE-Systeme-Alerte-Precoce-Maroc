"""
SAP Morocco — Alerts API.

Two access patterns:

  * GET /alerts/current      — today's pre-computed city alerts (GeoJSON file),
                               consumed by the Leaflet / Next.js heatmap overlay.
  * GET /alerts/point        — on-demand 7-day forecast for ANY lat/lon the user
                               clicks on the Moroccan map. Reads the latest raw
                               prediction tensor + climatology from the MinIO
                               DataLake and computes Heat Index / severity for the
                               nearest grid cell on the fly.
"""

from __future__ import annotations

import io
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import xarray as xr
from fastapi import APIRouter, HTTPException, Query

from app.core.meteo import (
    CH_RH,
    CH_TMAX,
    CH_TMIN,
    FORECAST_HORIZON,
    GRID_COLS,
    GRID_LATS,
    GRID_LONS,
    GRID_ROWS,
    in_domain,
    nearest_grid_index,
    noaa_heat_index,
    severity_to_alert_level,
)
from app.core.storage import (
    CLIMATOLOGY_KEY,
    PREDICTIONS_PREFIX,
    get_storage,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])

logger = logging.getLogger("api.alerts")

# ---------------------------------------------------------------------------
# Path configuration — resolves relative to the router module location
# ---------------------------------------------------------------------------
CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parents[2]            # backend/
PROJECT_ROOT = BACKEND_DIR.parent                # repo root
GEOJSON_PATH = PROJECT_ROOT / "public" / "data" / "today_alerts.geojson"

# In-memory cache for the heavy DataLake artifacts (raw prediction + climatology).
# Re-downloading them on every map click would be wasteful; refresh after TTL.
_CACHE_TTL_SECONDS = 600
_cache_lock = threading.Lock()
_cache: Dict[str, Any] = {"key": None, "loaded_at": 0.0, "pred": None, "tmax_90p": None, "tmin_10p": None}


# ---------------------------------------------------------------------------
# /alerts/current — today's pre-computed city alerts
# ---------------------------------------------------------------------------
def _read_geojson() -> Dict[str, Any]:
    """Read today_alerts.geojson; return an empty collection when missing/corrupt."""
    if not GEOJSON_PATH.exists():
        logger.warning("GeoJSON file not found: %s — returning empty collection", GEOJSON_PATH)
        return {"type": "FeatureCollection", "features": []}

    try:
        with open(GEOJSON_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError:
        logger.exception("Corrupted GeoJSON file — returning empty collection")
        return {"type": "FeatureCollection", "features": []}
    except OSError:
        logger.exception("Unable to read GeoJSON file")
        return {"type": "FeatureCollection", "features": []}


@router.get("/current", summary="Fetch today's heatwave / frost alerts")
async def get_current_alerts() -> Dict[str, Any]:
    """
    Returns a valid GeoJSON FeatureCollection with one Feature per monitored
    Moroccan city, each carrying its 7-day forecast in ``properties.forecasts``.
    """
    try:
        return _read_geojson()
    except Exception:
        logger.exception("Unhandled error reading alerts")
        raise HTTPException(status_code=500, detail="Failed to load alert data")


# ---------------------------------------------------------------------------
# /alerts/point — on-demand pixel forecast from the DataLake
# ---------------------------------------------------------------------------
def _load_prediction_bundle() -> Dict[str, Any]:
    """
    Fetch the latest raw prediction tensor [7, 3, 37, 65] and the climatology
    percentile maps from MinIO, with a short-lived in-process cache.
    """
    storage = get_storage()
    if storage is None:
        raise HTTPException(status_code=503, detail="DataLake (MinIO) is unavailable")

    pred_key = storage.latest_key(PREDICTIONS_PREFIX, suffix=".npy")
    if pred_key is None:
        raise HTTPException(
            status_code=404,
            detail="No prediction available yet — run the inference pipeline first",
        )

    now = time.time()
    with _cache_lock:
        fresh = (
            _cache["key"] == pred_key
            and _cache["pred"] is not None
            and (now - _cache["loaded_at"]) < _CACHE_TTL_SECONDS
        )
        if fresh:
            return _cache

        # ---- (re)load raw prediction tensor ----
        pred = np.load(io.BytesIO(storage.download_bytes(pred_key)))
        if pred.shape != (FORECAST_HORIZON, 3, GRID_ROWS, GRID_COLS):
            logger.error("Unexpected prediction shape %s for %s", pred.shape, pred_key)
            raise HTTPException(status_code=500, detail="Corrupted prediction tensor")

        # ---- load climatology percentiles (best-effort) ----
        tmax_90p = tmin_10p = None
        if storage.object_exists(CLIMATOLOGY_KEY):
            raw = storage.download_bytes(CLIMATOLOGY_KEY)
            ds = xr.open_dataset(io.BytesIO(raw), engine="h5netcdf")
            ds = ds.sel(latitude=slice(36, 27), longitude=slice(-17, -1))
            tmax_90p = ds["tmax_90p"].values.astype(np.float32)
            tmin_10p = ds["tmin_10p"].values.astype(np.float32)
            ds.close()
        else:
            logger.warning("Climatology not in DataLake — severity will use a 45 C fallback")
            tmax_90p = np.full((GRID_ROWS, GRID_COLS), 45.0, dtype=np.float32)
            tmin_10p = np.full((GRID_ROWS, GRID_COLS), 0.0, dtype=np.float32)

        _cache.update(
            key=pred_key, loaded_at=now, pred=pred, tmax_90p=tmax_90p, tmin_10p=tmin_10p
        )
        logger.info("Loaded prediction bundle from DataLake: %s", pred_key)
        return _cache


@router.get("/point", summary="On-demand 7-day forecast for a clicked map location")
async def get_point_forecast(
    lat: float = Query(..., ge=-90, le=90, description="Latitude in decimal degrees"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude in decimal degrees"),
) -> Dict[str, Any]:
    """
    Compute the 7-day forecast for the grid cell nearest to (lat, lon).

    Returns Tmax, Tmin, RH, Heat Index and the alert level for each of the
    7 forecast days, derived on the fly from the latest archived prediction
    tensor and the climatology percentiles stored in MinIO.
    """
    if not in_domain(lat, lon):
        raise HTTPException(
            status_code=422,
            detail=(
                f"({lat}, {lon}) is outside the model domain "
                f"[{GRID_LATS[-1]}..{GRID_LATS[0]} N, {GRID_LONS[0]}..{GRID_LONS[-1]} E]"
            ),
        )

    bundle = _load_prediction_bundle()
    pred = bundle["pred"]            # [7, 3, 37, 65]
    tmax_90p = bundle["tmax_90p"]    # [37, 65]
    tmin_10p = bundle["tmin_10p"]    # [37, 65]

    row, col = nearest_grid_index(lat, lon)
    start_date = datetime.utcnow()

    forecast: List[Dict[str, Any]] = []
    max_severity = -999.0

    for d in range(FORECAST_HORIZON):
        tmax_val = float(pred[d, CH_TMAX, row, col])
        tmin_val = float(pred[d, CH_TMIN, row, col])
        rh_val = float(pred[d, CH_RH, row, col])

        hi_val = noaa_heat_index(tmax_val, rh_val)

        heat_severity = tmax_val - float(tmax_90p[row, col])
        cold_severity = float(tmin_10p[row, col]) - tmin_val
        severity = max(heat_severity, cold_severity)
        max_severity = max(max_severity, severity)

        forecast.append(
            {
                "day": d,
                "date": (start_date + timedelta(days=d)).strftime("%Y-%m-%d"),
                "tmax": round(tmax_val, 1),
                "tmin": round(tmin_val, 1),
                "rh": round(rh_val, 1),
                "heat_index": round(hi_val, 1),
                "severity": round(max(0.0, severity), 1),
                "alert_level": severity_to_alert_level(severity),
            }
        )

    return {
        "query": {"lat": lat, "lon": lon},
        "grid_cell": {
            "row": row,
            "col": col,
            "lat": round(float(GRID_LATS[row]), 4),
            "lon": round(float(GRID_LONS[col]), 4),
        },
        "alert_level": severity_to_alert_level(max_severity),
        "severity": round(max(0.0, max_severity), 1),
        "forecast": forecast,
    }
