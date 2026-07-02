"""
NASA POWER surface producer (station-based, batch) for SAP Morocco — ingestion_3.

Fetches daily surface meteorology from the NASA POWER point API for each of the
30 Moroccan stations, applies the same unit conversions and derived targets as
the original `nasa_power_data.py`, and writes one raw CSV per station to
`data/raw/nasa_power/`. For every file written it publishes a JSON manifest to
Kafka (topic `nasa-power-raw`) unless `--no-kafka` is given.

Usage:
    python nasa_power_producer.py --start 2000-01-01 --end 2025-12-31 --no-kafka
    python nasa_power_producer.py --days 30                 # last 30 days, Kafka on
    python nasa_power_producer.py --stations "Ifrane,Dakhla" --no-kafka

Environment:
    KAFKA_BROKER          (default localhost:9092)
    KAFKA_TOPIC_NASA      (default nasa-power-raw)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
import requests

from features import heat_index, wind_chill
from kafka_bus import ManifestBus
from stations import STATIONS, distance_to_ocean, slug

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "nasa_power"

KAFKA_TOPIC = os.getenv("KAFKA_TOPIC_NASA", "nasa-power-raw")
PARAMETERS = "T2M_MAX,T2M_MIN,T2M,RH2M,WS10M,WD10M,PS,PRECTOTCORR,ALLSKY_SFC_SW_DWN"
MAX_RETRIES = 3
RETRY_DELAY_S = 10

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("NASA-Producer")


def _date_range(start: Optional[str], end: Optional[str], days_back: Optional[int]) -> tuple[str, str]:
    """Resolve start/end as YYYYMMDD (NASA POWER format)."""
    if days_back is not None:
        end_d = datetime.now(timezone.utc).date() - timedelta(days=1)
        start_d = end_d - timedelta(days=days_back - 1)
    else:
        start_d = datetime.strptime(start, "%Y-%m-%d").date()
        end_d = datetime.strptime(end, "%Y-%m-%d").date()
    return start_d.strftime("%Y%m%d"), end_d.strftime("%Y%m%d")


def _fetch(lat: float, lon: float, start: str, end: str) -> dict:
    url = (
        "https://power.larc.nasa.gov/api/temporal/daily/point?"
        f"parameters={PARAMETERS}&community=RE"
        f"&longitude={lon}&latitude={lat}&start={start}&end={end}&format=JSON"
    )
    last_exc: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, timeout=90)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001 - retried
            last_exc = exc
            logger.warning("Fetch attempt %d/%d failed: %s", attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_S)
    raise RuntimeError(f"NASA POWER fetch failed for ({lat},{lon}): {last_exc}")


def _to_dataframe(payload: dict, st: dict, dist_ocean: float) -> pd.DataFrame:
    elevation = payload["geometry"]["coordinates"][2]
    df = pd.DataFrame(payload["properties"]["parameter"])
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    df = df.reset_index().rename(columns={"index": "date"})

    df = df.replace(-999.0, np.nan).interpolate(method="linear").ffill().bfill()

    df["Press_hPa"] = df["PS"] * 10                       # kPa -> hPa
    df["Solar_Jm2"] = df["ALLSKY_SFC_SW_DWN"] * 3_600_000  # kW-hr/m^2/day -> J/m^2
    wdir_rad = np.radians(df["WD10M"])
    df["u_wind"] = -df["WS10M"] * np.sin(wdir_rad)
    df["v_wind"] = -df["WS10M"] * np.cos(wdir_rad)

    out = pd.DataFrame({
        "date": df["date"].dt.date,
        "Tmax": df["T2M_MAX"], "Tmin": df["T2M_MIN"], "Tmean": df["T2M"],
        "RH": df["RH2M"], "WindSpeed_ms": df["WS10M"],
        "u_wind": df["u_wind"], "v_wind": df["v_wind"],
        "Press_hPa": df["Press_hPa"], "Solar_Jm2": df["Solar_Jm2"],
        "Precipitation_mm": df["PRECTOTCORR"],
    })
    out["HeatIndex"] = heat_index(out["Tmax"], out["RH"])
    out["WindChill"] = wind_chill(out["Tmin"], out["WindSpeed_ms"])
    out["latitude"] = st["lat"]
    out["longitude"] = st["lon"]
    out["elevation_m"] = elevation
    out["distance_to_ocean_km"] = round(dist_ocean, 2)
    return out


def _select(names: Optional[str]) -> List[dict]:
    if not names:
        return STATIONS
    wanted = {n.strip().lower() for n in names.split(",")}
    return [s for s in STATIONS if str(s["station"]).lower() in wanted]


def main() -> None:
    ap = argparse.ArgumentParser(description="NASA POWER station producer (ingestion_3)")
    ap.add_argument("--start", help="YYYY-MM-DD")
    ap.add_argument("--end", help="YYYY-MM-DD")
    ap.add_argument("--days", type=int, help="last N days instead of --start/--end")
    ap.add_argument("--stations", help="comma-separated station names (default: all 30)")
    ap.add_argument("--no-kafka", action="store_true", help="batch mode, skip manifest publishing")
    args = ap.parse_args()

    if args.days is None and not (args.start and args.end):
        args.start, args.end = "2000-01-01", "2025-12-31"  # documented historical default

    start, end = _date_range(args.start, args.end, args.days)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stations = _select(args.stations)
    bus = ManifestBus(enabled=not args.no_kafka)
    logger.info("NASA POWER %s -> %s | %d stations -> %s", start, end, len(stations), RAW_DIR)

    ok = 0
    for i, st in enumerate(stations, 1):
        name = str(st["station"])
        logger.info("[%d/%d] %s", i, len(stations), name)
        try:
            payload = _fetch(st["lat"], st["lon"], start, end)
            df = _to_dataframe(payload, st, distance_to_ocean(st["lat"], st["lon"]))
            out_path = RAW_DIR / f"{slug(name)}.csv"
            df.to_csv(out_path, index=False)
            ok += 1
            logger.info("  saved %d rows -> %s", len(df), out_path.name)
            bus.publish(KAFKA_TOPIC, key=slug(name), manifest={
                "source": "nasa_power", "station": name, "path": str(out_path),
                "rows": int(len(df)),
                "date_start": str(df["date"].min()), "date_end": str(df["date"].max()),
            })
            time.sleep(1)  # courtesy to NASA servers
        except Exception:
            logger.exception("  FAILED %s", name)

    bus.flush()
    logger.info("Done: %d/%d stations written.", ok, len(stations))


if __name__ == "__main__":
    main()
