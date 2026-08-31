"""
Shared station registry for the ingestion_3 station-based pipeline.

Both producers (NASA POWER surface, NOAA NCEP upper-air) and the processor
import the *same* station list and geo helpers from here so the 30 Moroccan
stations stay perfectly aligned across sources (single source of truth).
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# 30 Moroccan stations (station, city, lat, lon)
# ---------------------------------------------------------------------------
STATIONS: List[Dict[str, object]] = [
    {"station": "Agadir Inezgane", "city": "Agadir", "lat": 30.383, "lon": -9.567},
    {"station": "Agadir Al Massira", "city": "Agadir", "lat": 30.319, "lon": -9.383},
    {"station": "Essaouira", "city": "Essaouira", "lat": 31.517, "lon": -9.783},
    {"station": "Marrakech Menara", "city": "Marrakech", "lat": 31.617, "lon": -8.032},
    {"station": "Ouarzazate", "city": "Ouarzazate", "lat": 30.933, "lon": -6.900},
    {"station": "Taroudant", "city": "Taroudant", "lat": 30.500, "lon": -8.817},
    {"station": "Tiznit", "city": "Tiznit", "lat": 29.683, "lon": -9.733},
    {"station": "Guelmim", "city": "Guelmim", "lat": 29.017, "lon": -10.050},
    {"station": "Tan-Tan", "city": "Tan-Tan", "lat": 28.450, "lon": -11.150},
    {"station": "Casablanca Anfa", "city": "Casablanca", "lat": 33.567, "lon": -7.667},
    {"station": "Nouasseur", "city": "Casablanca", "lat": 33.367, "lon": -7.583},
    {"station": "Rabat-Salé", "city": "Rabat", "lat": 34.050, "lon": -6.767},
    {"station": "Kénitra", "city": "Kénitra", "lat": 34.300, "lon": -6.600},
    {"station": "Fès-Saïss", "city": "Fès", "lat": 33.933, "lon": -4.983},
    {"station": "Meknès", "city": "Meknès", "lat": 33.883, "lon": -5.533},
    {"station": "Ifrane", "city": "Ifrane", "lat": 33.500, "lon": -5.167},
    {"station": "Midelt", "city": "Midelt", "lat": 32.683, "lon": -4.733},
    {"station": "Errachidia", "city": "Errachidia", "lat": 31.967, "lon": -4.417},
    {"station": "Beni Mellal", "city": "Beni Mellal", "lat": 32.367, "lon": -6.400},
    {"station": "Khouribga", "city": "Khouribga", "lat": 32.867, "lon": -6.967},
    {"station": "Oujda Angads", "city": "Oujda", "lat": 34.783, "lon": -1.933},
    {"station": "Nador Aroui", "city": "Nador", "lat": 34.983, "lon": -3.017},
    {"station": "Al Hoceima", "city": "Al Hoceima", "lat": 35.183, "lon": -3.850},
    {"station": "Tétouan Sania Ramel", "city": "Tétouan", "lat": 35.583, "lon": -5.333},
    {"station": "Tangier Boukhalef", "city": "Tangier", "lat": 35.733, "lon": -5.900},
    {"station": "Larache", "city": "Larache", "lat": 35.183, "lon": -6.133},
    {"station": "Sidi Ifni", "city": "Sidi Ifni", "lat": 29.367, "lon": -10.183},
    {"station": "Safi", "city": "Safi", "lat": 32.283, "lon": -9.233},
    {"station": "Dakhla", "city": "Dakhla", "lat": 23.700, "lon": -15.867},
    {"station": "Laâyoune", "city": "Laâyoune", "lat": 27.933, "lon": -13.217},
]

# Moroccan coastline reference points (lat, lon) for distance-to-ocean.
COASTLINE_POINTS: List[Tuple[float, float]] = [
    (35.08, -2.23), (35.25, -3.93), (35.78, -5.81), (34.26, -6.66), (34.02, -6.84),
    (33.60, -7.63), (33.25, -8.50), (32.30, -9.23), (31.51, -9.77), (30.42, -9.59),
    (29.38, -10.17), (28.49, -11.32), (27.93, -12.92), (27.09, -13.41), (26.12, -14.48),
    (23.71, -15.93), (21.32, -16.96),
]


def slug(station_name: str) -> str:
    """Canonical filesystem-safe id used in every filename across the pipeline."""
    return station_name.replace(" ", "_").replace("-", "_")


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return r * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def distance_to_ocean(lat: float, lon: float) -> float:
    """Minimum distance (km) from a point to the Moroccan coastline reference set."""
    return min(haversine_distance(lat, lon, clat, clon) for clat, clon in COASTLINE_POINTS)
