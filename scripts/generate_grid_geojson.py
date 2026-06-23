"""
Generate a full-grid GeoJSON FeatureCollection for the SAP Morocco map overlay.

Produces 37 × 65 = 2405 polygon features (one per grid cell), each carrying
a realistic 7-day forecast with Tmax, Tmin, RH, Heat Index, severity, and
alert_level.  The output is written to ``public/data/today_alerts.geojson``
(replacing the old city-point file) so the frontend can render a continuous
grid-colored heat map.

Replicates the logic in ``backend/app/core/meteo.py`` so the mock data is
structurally identical to what the real inference pipeline produces — just
with synthetic values for frontend development.

Usage:
    python scripts/generate_grid_geojson.py
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Grid constants (must match backend/app/core/meteo.py)
# ---------------------------------------------------------------------------
GRID_LAT_NORTH = 36.0
GRID_LAT_SOUTH = 27.0
GRID_LON_WEST = -17.0
GRID_LON_EAST = -1.0
GRID_ROWS = 37
GRID_COLS = 65
FORECAST_HORIZON = 7

GRID_LATS = np.linspace(GRID_LAT_NORTH, GRID_LAT_SOUTH, GRID_ROWS)
GRID_LONS = np.linspace(GRID_LON_WEST, GRID_LON_EAST, GRID_COLS)

# ---------------------------------------------------------------------------
# NOAA Heat Index (same as backend/app/core/meteo.py:noaa_heat_index)
# ---------------------------------------------------------------------------
def noaa_heat_index(t_celsius: float, rh_percent: float) -> float:
    if t_celsius < 26.7:
        return t_celsius

    t_f = t_celsius * 9.0 / 5.0 + 32.0
    rh = rh_percent

    hi_f = (
        -42.379
        + 2.04901523 * t_f
        + 10.14333127 * rh
        - 0.22475541 * t_f * rh
        - 6.83783e-3 * t_f**2
        - 5.481717e-2 * rh**2
        + 1.22874e-3 * t_f**2 * rh
        + 8.5282e-4 * t_f * rh**2
        - 1.99e-6 * t_f**2 * rh**2
    )

    if rh < 13.0 and 80.0 <= t_f <= 112.0:
        adjustment = ((13.0 - rh) / 4.0) * ((17.0 - abs(t_f - 95.0)) / 17.0) ** 0.5
        hi_f -= adjustment
    elif rh > 85.0 and 80.0 <= t_f <= 87.0:
        adjustment = ((rh - 85.0) / 10.0) * ((87.0 - t_f) / 5.0)
        hi_f += adjustment

    hi_c = (hi_f - 32.0) * 5.0 / 9.0
    return max(t_celsius, hi_c)


def severity_to_alert_level(severity: float) -> str:
    if severity <= 0.0:
        return "none"
    if severity > 5.0:
        return "red"
    if severity > 2.0:
        return "orange"
    return "yellow"


# ---------------------------------------------------------------------------
# Mock climatology — spatially smooth
# ---------------------------------------------------------------------------
def _make_mock_climatology() -> np.ndarray:
    """Return a 37×65 grid of 90th-percentile tmax values (deg C).

    Warmer in the south / interior, cooler near the Atlantic coast and
    in the north.  Synthetic but geographically plausible for Morocco.
    """
    lats_2d = np.broadcast_to(GRID_LATS[:, None], (GRID_ROWS, GRID_COLS))
    lons_2d = np.broadcast_to(GRID_LONS[None, :], (GRID_ROWS, GRID_COLS))

    base = 38.0 - 0.4 * (lats_2d - 27.0)  # hotter in the south
    coastal = 6.0 * np.exp(-((lons_2d + 9.0) ** 2) / 80.0)  # cooler near Atlantic
    atlas = -3.0 * np.exp(-((lats_2d - 32.0) ** 2 + (lons_2d + 6.0) ** 2) / 15.0)  # Atlas mtns

    tmax_90p = base - coastal + atlas
    tmax_90p = np.clip(tmax_90p, 20.0, 48.0)
    return tmax_90p.astype(np.float32)


def _make_mock_forecasts(
    row: int, col: int, tmax_90p: np.ndarray, start_date: datetime
) -> tuple[list[dict], float]:
    """Generate a 7-day forecast for a single grid cell.

    Returns (forecast_list, max_severity).
    """
    lat = float(GRID_LATS[row])
    lon = float(GRID_LONS[col])

    base_tmax = float(tmax_90p[row, col])
    rng = np.random.default_rng(seed=row * GRID_COLS + col)
    day_variation = rng.uniform(-3.0, 4.0, size=FORECAST_HORIZON)
    if rng.random() < 0.08:
        day_variation += rng.uniform(2.0, 6.0, size=FORECAST_HORIZON)

    forecasts = []
    max_severity = -999.0

    for d in range(FORECAST_HORIZON):
        tmax_val = base_tmax + day_variation[d]
        tmin_val = tmax_val - np.random.default_rng(seed=d * 100 + row * GRID_COLS + col).uniform(8.0, 16.0)

        rh_val = 60.0 - 0.7 * abs(lon + 9.0) + np.random.default_rng(seed=1000 + d * 100 + row * GRID_COLS + col).uniform(-10.0, 10.0)
        rh_val = max(5.0, min(95.0, rh_val))

        hi_val = noaa_heat_index(tmax_val, rh_val)

        severity = tmax_val - base_tmax
        max_severity = max(max_severity, severity)

        forecast_date = (start_date + timedelta(days=d)).strftime("%Y-%m-%d")
        forecasts.append({
            "day": d,
            "date": forecast_date,
            "tmax": round(tmax_val, 1),
            "tmin": round(tmin_val, 1),
            "rh": round(rh_val, 1),
            "heat_index": round(hi_val, 1),
            "severity": round(max(0.0, severity), 1),
            "alert_level": severity_to_alert_level(severity),
        })

    return forecasts, max_severity


def _build_polygon_coords(row: int, col: int) -> list[list[list[float]]]:
    """Build a [lon, lat] Polygon ring for the grid cell at (row, col).

    Rectangular cells with 0.25-degree edges.
    """
    lat_min = float(GRID_LATS[row] - (GRID_LAT_NORTH - GRID_LAT_SOUTH) / (2 * GRID_ROWS))
    lat_max = float(GRID_LATS[row] + (GRID_LAT_NORTH - GRID_LAT_SOUTH) / (2 * GRID_ROWS))
    lon_min = float(GRID_LONS[col] - (GRID_LON_EAST - GRID_LON_WEST) / (2 * GRID_COLS))
    lon_max = float(GRID_LONS[col] + (GRID_LON_EAST - GRID_LON_WEST) / (2 * GRID_COLS))

    ring = [
        [lon_min, lat_min],
        [lon_max, lat_min],
        [lon_max, lat_max],
        [lon_min, lat_max],
        [lon_min, lat_min],
    ]
    return [ring]


def generate_grid_geojson() -> dict:
    """Build a FeatureCollection with 2405 Polygon features."""
    tmax_90p = _make_mock_climatology()
    start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    features = []

    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            forecasts, max_severity = _make_mock_forecasts(row, col, tmax_90p, start_date)
            lat_center = round(float(GRID_LATS[row]), 4)
            lon_center = round(float(GRID_LONS[col]), 4)

            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": _build_polygon_coords(row, col),
                },
                "properties": {
                    "row": row,
                    "col": col,
                    "lat": lat_center,
                    "lon": lon_center,
                    "alert_level": severity_to_alert_level(max_severity),
                    "severity": round(max(0.0, max_severity), 1),
                    "forecasts": forecasts,
                },
            }
            features.append(feature)

    print(f"Generated {len(features)} grid cell features")
    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    output_path = project_root / "public" / "data" / "today_alerts.geojson"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    geojson = generate_grid_geojson()

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(geojson, fh, indent=2)

    print(f"Written -> {output_path} ({output_path.stat().st_size / 1024:.0f} KB)")
