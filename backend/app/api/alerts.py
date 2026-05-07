"""
SAP Morocco — Alerts API.

Provides real-time access to today's weather alerts in GeoJSON format
consumable by a Leaflet / Next.js frontend.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/alerts", tags=["alerts"])

logger = logging.getLogger("api.alerts")

# ---------------------------------------------------------------------------
# Path configuration — resolves relative to the router module location
# ---------------------------------------------------------------------------
CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR  = CURRENT_FILE.parents[2]                       # backend/
PROJECT_ROOT = BACKEND_DIR.parent                            # repo root
GEOJSON_PATH = PROJECT_ROOT / "public" / "data" / "today_alerts.geojson"


def _read_geojson() -> Dict[str, Any]:
    """
    Read and parse today_alerts.geojson.

    Returns an empty FeatureCollection when the file does not exist yet
    (e.g. before the first inference run completes).
    """
    if not GEOJSON_PATH.exists():
        logger.warning("GeoJSON file not found: %s — returning empty collection", GEOJSON_PATH)
        return {"type": "FeatureCollection", "features": []}

    try:
        with open(GEOJSON_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data
    except json.JSONDecodeError:
        logger.exception("Corrupted GeoJSON file — returning empty collection")
        return {"type": "FeatureCollection", "features": []}
    except OSError:
        logger.exception("Unable to read GeoJSON file")
        return {"type": "FeatureCollection", "features": []}


@router.get("/current", summary="Fetch today's heatwave / frost alerts")
async def get_current_alerts() -> Dict[str, Any]:
    """
    Returns a valid GeoJSON FeatureCollection where each Feature represents
    an anomalous pixel.

    Properties per feature:
      - region_lat, region_lon  : grid cell center coordinates
      - alert_level             : 'red' | 'orange' | 'yellow'
      - predicted_temp          : predicted maximum temperature (°C)
      - severity                : degrees above the 90th percentile climatology

    The frontend (Next.js + Leaflet) maps these points as a heatmap overlay.
    """
    try:
        geojson = _read_geojson()
    except Exception:
        logger.exception("Unhandled error reading alerts")
        raise HTTPException(status_code=500, detail="Failed to load alert data")

    return geojson
