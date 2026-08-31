"""
NOAA NCEP upper-air producer (Z500 & T850, station-based, batch) — ingestion_3.

For each requested year, downloads the global daily-average geopotential-height
(`hgt`) and temperature (`air`) NetCDF files from NOAA PSL, extracts the nearest
grid point for each of the 30 stations at 500 hPa / 850 hPa, and appends one raw
CSV per station to `data/raw/upperair/`. Publishes a JSON manifest per station to
Kafka (topic `upperair-raw`) unless `--no-kafka`.

Mirrors the logic of the original `z500_t850.py` but with logging, retries,
shared station registry and the optional manifest bus.

Usage:
    python upperair_producer.py --start-year 1990 --end-year 2025 --no-kafka
    python upperair_producer.py --start-year 2024 --end-year 2025      # Kafka on

Environment:
    KAFKA_BROKER             (default localhost:9092)
    KAFKA_TOPIC_UPPERAIR     (default upperair-raw)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import List

import pandas as pd
import requests
import xarray as xr

from kafka_bus import ManifestBus
from stations import STATIONS, slug

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "upperair"
TMP_DIR = RAW_DIR / "tmp"

KAFKA_TOPIC = os.getenv("KAFKA_TOPIC_UPPERAIR", "upperair-raw")
VARIABLES = {"hgt": "z", "air": "t"}     # source var -> nice prefix
TARGET_LEVELS = [500.0, 850.0]
KEEP_COLS = ["date", "z_500hPa", "t_850hPa"]
MAX_RETRIES = 3
RETRY_DELAY_S = 30

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("UpperAir-Producer")


def _download(url: str, local_path: Path) -> bool:
    if local_path.exists() and local_path.stat().st_size > 1024:
        return True
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with requests.get(url, stream=True, timeout=180) as resp:
                resp.raise_for_status()
                with open(local_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1 << 20):
                        if chunk:
                            f.write(chunk)
            return True
        except Exception as exc:  # noqa: BLE001 - retried
            logger.warning("download %s attempt %d/%d failed: %s",
                           local_path.name, attempt, MAX_RETRIES, exc)
            local_path.unlink(missing_ok=True)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_S)
    return False


def _extract_year(ds_year: xr.Dataset, st: dict) -> pd.DataFrame:
    lon_360 = (st["lon"] + 360) % 360                      # NOAA uses 0..360 longitude
    station_ds = ds_year.sel(lat=st["lat"], lon=lon_360, method="nearest")
    df = station_ds.to_dataframe().reset_index()
    pivot = df.pivot_table(index="time", columns="level", values=list(VARIABLES.keys()))
    pivot.columns = [f"{VARIABLES[var]}_{int(level)}hPa" for var, level in pivot.columns]
    pivot = pivot.reset_index()
    pivot["date"] = pivot["time"].dt.date
    present = [c for c in KEEP_COLS if c in pivot.columns]
    out = pivot[present].copy()
    if "t_850hPa" in out.columns:
        out["t_850hPa"] = out["t_850hPa"] - 273.15         # K -> °C
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="NOAA NCEP Z500/T850 producer (ingestion_3)")
    ap.add_argument("--start-year", type=int, default=1990)
    ap.add_argument("--end-year", type=int, default=2025)
    ap.add_argument("--no-kafka", action="store_true", help="batch mode, skip manifest publishing")
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    bus = ManifestBus(enabled=not args.no_kafka)
    rows_per_station: dict[str, int] = {}

    for year in range(args.start_year, args.end_year + 1):
        logger.info("--- Year %d ---", year)
        files: List[Path] = []
        ok = True
        for var in VARIABLES:
            url = (f"https://downloads.psl.noaa.gov/Datasets/ncep.reanalysis.dailyavgs/"
                   f"pressure/{var}.{year}.nc")
            local = TMP_DIR / f"{var}_{year}.nc"
            if _download(url, local):
                files.append(local)
            else:
                ok = False
                break
        if not ok:
            logger.error("Skipping %d (download failure).", year)
            continue

        datasets: List[xr.Dataset] = []
        try:
            datasets = [xr.open_dataset(f).sel(level=TARGET_LEVELS) for f in files]
            ds_year = xr.merge(datasets, compat="override")
            for st in STATIONS:
                name = str(st["station"])
                out = _extract_year(ds_year, st)
                out_path = RAW_DIR / f"{slug(name)}_upperair.csv"
                header = not out_path.exists()
                out.to_csv(out_path, mode="a", header=header, index=False)
                rows_per_station[name] = rows_per_station.get(name, 0) + len(out)
            logger.info("  extracted %d stations for %d", len(STATIONS), year)
        except Exception:
            logger.exception("  processing failed for %d", year)
        finally:
            for ds in datasets:
                try:
                    ds.close()
                except Exception:
                    pass
            for f in files:
                f.unlink(missing_ok=True)

    # One manifest per station after all years appended.
    for st in STATIONS:
        name = str(st["station"])
        out_path = RAW_DIR / f"{slug(name)}_upperair.csv"
        if out_path.exists():
            bus.publish(KAFKA_TOPIC, key=slug(name), manifest={
                "source": "upperair", "station": name, "path": str(out_path),
                "rows": rows_per_station.get(name, 0),
                "year_start": args.start_year, "year_end": args.end_year,
            })
    bus.flush()
    logger.info("Upper-air collection complete (%d..%d).", args.start_year, args.end_year)


if __name__ == "__main__":
    main()
