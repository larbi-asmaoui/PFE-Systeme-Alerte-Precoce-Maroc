"""
Build the station-history payload for the dashboard's "Historique Stations" page.

Reads the cleaned GSOD histories in ``data/cleandata_gsod_by_station`` (1990 →
2025, one CSV per station) and emits a single compact JSON —
``public/data/stations_history.json`` — with, per station:

  * ``meta``       — id, name, lat/lon, elevation, data span, #years, #records
  * ``monthly``    — 12-point climatology (mean tmax / tmin / heat_index /
                     wind_chill) used for the seasonal-cycle chart
  * ``annual``     — one point per year (mean tmax, mean heat_index, mean
                     wind_chill) used for the long-term-trend chart
  * ``records``    — hottest day (max heat_index + date) and coldest day
                     (min wind_chill + date)
  * ``recent``     — the last 90 daily observations (date, heat_index,
                     wind_chill) for the recent-conditions chart

Everything is rounded to 1 decimal and the recent window is capped, so the whole
file stays small (a few hundred KB) and loads instantly in the browser.

Usage
-----
    python scripts/build_station_history.py
"""

from __future__ import annotations

import glob
import json
import logging
import os
from typing import Any, Dict, List

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("build_station_history")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIONS_DIR = os.path.join(ROOT, "data", "cleandata_gsod_by_station")
# Real Open-Meteo data merged on top of the GSOD archive so the recent window /
# records / end-date reach today, with no synthetic fill:
#   GAP_DIR  — ERA5 archive backfill (openmeteo/backfill_openmeteo.py) covering
#              the months between the GSOD end and the live week.
#   LIVE_DIR — the last ~7 days from the forecast endpoint (openmeteo_producer).
# On overlapping dates, live wins over gap wins over archive.
GAP_DIR = os.path.join(ROOT, "data", "live", "openmeteo_gap")
LIVE_DIR = os.path.join(ROOT, "data", "live", "openmeteo")
OUT_PATH = os.path.join(ROOT, "public", "data", "stations_history.json")

RECENT_DAYS = 90
# Minimum daily observations for a year to appear in the long-term trend, so a
# partial year (e.g. a current year still in progress) doesn't skew the line.
MIN_OBS_PER_YEAR = 300
MONTHS_FR = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]


def _r(x: Any) -> float | None:
    """Round to 1 dp, mapping NaN -> None so it serialises as JSON null."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    return round(float(x), 1)


def _load_with_live(csv_path: str) -> pd.DataFrame:
    """GSOD archive + ERA5 gap backfill + live forecast for one station.

    All three sources are real (measured / reanalysis), concatenated oldest-source
    first so that on any overlapping date the most recent source wins:
    ``gsod  <  gap(archive)  <  live(forecast)``. The result is a continuous daily
    series from 1990 to today with no synthetic fill.
    """
    code = os.path.basename(csv_path).replace("_cleaned.csv", "")
    frames = [pd.read_csv(csv_path, parse_dates=["date"])]
    for d in (GAP_DIR, LIVE_DIR):  # order matters: later dirs win on overlap
        p = os.path.join(d, f"{code}_cleaned.csv")
        if os.path.exists(p):
            frames.append(pd.read_csv(p, parse_dates=["date"]))
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset="date", keep="last")
    return df.sort_values("date").reset_index(drop=True)


def build_station(csv_path: str) -> Dict[str, Any] | None:
    df = _load_with_live(csv_path)
    if df.empty:
        return None
    df["month"] = df["date"].dt.month
    df["year"] = df["date"].dt.year

    row = df.iloc[-1]
    code = os.path.basename(csv_path).replace("_cleaned.csv", "")

    # --- monthly climatology (mean over all years) ---
    m = df.groupby("month")[["tmax_c", "tmin_c", "heat_index", "wind_chill"]].mean()
    monthly = [
        {
            "month": MONTHS_FR[mm - 1],
            "tmax": _r(m.loc[mm, "tmax_c"]) if mm in m.index else None,
            "tmin": _r(m.loc[mm, "tmin_c"]) if mm in m.index else None,
            "heat_index": _r(m.loc[mm, "heat_index"]) if mm in m.index else None,
            "wind_chill": _r(m.loc[mm, "wind_chill"]) if mm in m.index else None,
        }
        for mm in range(1, 13)
    ]

    # --- annual means (long-term trend) — drop sparse years (partial current) ---
    counts = df.groupby("year").size()
    a = df.groupby("year")[["tmax_c", "heat_index", "wind_chill"]].mean()
    annual = [
        {
            "year": int(yy),
            "tmax": _r(a.loc[yy, "tmax_c"]),
            "heat_index": _r(a.loc[yy, "heat_index"]),
            "wind_chill": _r(a.loc[yy, "wind_chill"]),
        }
        for yy in a.index
        if counts.loc[yy] >= MIN_OBS_PER_YEAR
    ]

    # --- records ---
    hot = df.loc[df["heat_index"].idxmax()]
    cold = df.loc[df["wind_chill"].idxmin()]
    records = {
        "hottest": {"value": _r(hot["heat_index"]), "date": hot["date"].strftime("%Y-%m-%d")},
        "coldest": {"value": _r(cold["wind_chill"]), "date": cold["date"].strftime("%Y-%m-%d")},
    }

    # --- recent daily window ---
    recent = [
        {"date": r["date"].strftime("%Y-%m-%d"), "heat_index": _r(r["heat_index"]), "wind_chill": _r(r["wind_chill"])}
        for _, r in df.tail(RECENT_DAYS).iterrows()
    ]

    return {
        "meta": {
            "code": code,
            "station_id": str(row.get("station_id", "")),
            "station_name": str(row.get("station_name", "")) or code,
            "lat": _r(row["latitude"]),
            "lon": _r(row["longitude"]),
            "elevation": _r(row["elevation"]),
            "start": df["date"].min().strftime("%Y-%m-%d"),
            "end": df["date"].max().strftime("%Y-%m-%d"),
            "n_years": int(df["year"].nunique()),
            "n_obs": int(len(df)),
        },
        "monthly": monthly,
        "annual": annual,
        "records": records,
        "recent": recent,
    }


def main() -> int:
    csvs = sorted(glob.glob(os.path.join(STATIONS_DIR, "*_cleaned.csv")))
    if not csvs:
        raise FileNotFoundError(f"No *_cleaned.csv in {STATIONS_DIR}")

    stations: List[Dict[str, Any]] = []
    for path in csvs:
        st = build_station(path)
        if st is None:
            continue
        stations.append(st)
        logger.info(
            "%-28s %s..%s  %d yrs  hot=%.1f cold=%.1f",
            st["meta"]["station_name"], st["meta"]["start"], st["meta"]["end"],
            st["meta"]["n_years"], st["records"]["hottest"]["value"], st["records"]["coldest"]["value"],
        )

    stations.sort(key=lambda s: s["meta"]["station_name"])
    payload = {
        "generated_from": "data/cleandata_gsod_by_station",
        "n_stations": len(stations),
        "stations": stations,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    size_kb = os.path.getsize(OUT_PATH) / 1024
    logger.info("Wrote %d stations -> %s (%.0f KB)", len(stations), OUT_PATH, size_kb)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
