"""
Shared meteorological helpers for SAP Morocco.

This module holds the *pure* (NumPy-only, no PyTorch) primitives that are reused
by both the offline inference job (``backend/predictor.py``) and the online
FastAPI point-query endpoint (``backend/app/api/alerts.py``):

  * the fixed model grid (37 lat x 65 lon over the Morocco bounding box),
  * nearest-grid-cell lookup,
  * the NOAA Rothfusz Heat Index regression,
  * the severity -> alert-level mapping,
  * the list of major Moroccan cities.

Keeping these here avoids importing the heavy ``predictor`` module (and therefore
torch) inside the API process.
"""

from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# Model grid — Morocco bounding box [36, -17, 27, -1] at 0.25 deg
# ---------------------------------------------------------------------------
GRID_LAT_NORTH = 36.0
GRID_LAT_SOUTH = 27.0
GRID_LON_WEST = -17.0
GRID_LON_EAST = -1.0
GRID_ROWS = 37
GRID_COLS = 65

# latitudes are descending (north -> south), longitudes ascending (west -> east)
GRID_LATS = np.linspace(GRID_LAT_NORTH, GRID_LAT_SOUTH, GRID_ROWS)
GRID_LONS = np.linspace(GRID_LON_WEST, GRID_LON_EAST, GRID_COLS)

FORECAST_HORIZON = 7  # days

# Target channel order produced by the model: [tmax, tmin, rh]
CH_TMAX, CH_TMIN, CH_RH = 0, 1, 2

# ---------------------------------------------------------------------------
# Major Moroccan cities (lat, lon in decimal degrees)
# ---------------------------------------------------------------------------
MOROCCO_CITIES = [
    {"name": "Casablanca",  "lat": 33.5731, "lon": -7.5898},
    {"name": "Rabat",       "lat": 34.0209, "lon": -6.8416},
    {"name": "Marrakech",   "lat": 31.6295, "lon": -7.9811},
    {"name": "Agadir",      "lat": 30.4278, "lon": -9.5981},
    {"name": "Taroudant",   "lat": 30.4728, "lon": -8.8732},
    {"name": "Fès",         "lat": 34.0331, "lon": -5.0003},
    {"name": "Tanger",      "lat": 35.7595, "lon": -5.8340},
    {"name": "Meknès",      "lat": 33.8920, "lon": -5.5510},
    {"name": "Oujda",       "lat": 34.6814, "lon": -1.9086},
    {"name": "Kénitra",     "lat": 34.2610, "lon": -6.5802},
    {"name": "Tétouan",     "lat": 35.5889, "lon": -5.3626},
    {"name": "Safi",        "lat": 32.2994, "lon": -9.2372},
    {"name": "Mohammédia",  "lat": 33.3093, "lon": -8.4552},
    {"name": "Béni Mellal", "lat": 32.3373, "lon": -6.3498},
    {"name": "Nador",       "lat": 35.1667, "lon": -2.9333},
    {"name": "Taza",        "lat": 34.2155, "lon": -4.0120},
    {"name": "Settat",      "lat": 33.0010, "lon": -7.6166},
    {"name": "Khouribga",   "lat": 32.8811, "lon": -6.9063},
    {"name": "Errachidia",  "lat": 31.9314, "lon": -4.4244},
    {"name": "Laâyoune",    "lat": 27.1525, "lon": -13.2003},
    {"name": "Al Hoceïma",  "lat": 35.2442, "lon": -3.9317},
    {"name": "Essaouira",   "lat": 31.5125, "lon": -9.7700},
    {"name": "Guelmim",     "lat": 28.9884, "lon": -10.0633},
]


# ---------------------------------------------------------------------------
# Grid helpers
# ---------------------------------------------------------------------------
def in_domain(lat: float, lon: float) -> bool:
    """True when (lat, lon) falls inside the model's spatial domain."""
    return (GRID_LAT_SOUTH <= lat <= GRID_LAT_NORTH) and (
        GRID_LON_WEST <= lon <= GRID_LON_EAST
    )


def nearest_grid_index(lat: float, lon: float) -> tuple[int, int]:
    """Return the (row, col) of the grid cell nearest to (lat, lon)."""
    row = int(np.abs(GRID_LATS - lat).argmin())
    col = int(np.abs(GRID_LONS - lon).argmin())
    return row, col


# ---------------------------------------------------------------------------
# NOAA Rothfusz Heat Index
# ---------------------------------------------------------------------------
def noaa_heat_index(t_celsius: float, rh_percent: float) -> float:
    """
    NOAA Rothfusz regression for the Heat Index.

    Converts Celsius to Fahrenheit, computes HI in deg F, then back to deg C.
    Below 26.7 deg C the regression is not valid, so the dry temperature is
    returned unchanged.

    Reference: https://www.weather.gov/media/epz/wxcalc/heatIndex.pdf
    """
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


# ---------------------------------------------------------------------------
# Severity -> alert level
# ---------------------------------------------------------------------------
def severity_to_alert_level(severity: float) -> str:
    """Map a 'degrees above the 90th-percentile climatology' value to a level."""
    if severity <= 0.0:
        return "none"
    if severity > 5.0:
        return "red"
    if severity > 2.0:
        return "orange"
    return "yellow"
