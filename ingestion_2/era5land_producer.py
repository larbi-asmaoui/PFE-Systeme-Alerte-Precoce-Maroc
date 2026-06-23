"""
ERA5 / ERA5-Land ingestion producer for SAP Morocco.

Downloads hourly data from the Copernicus Climate Data Store (CDS) for the
Morocco bounding-box region, saves one NetCDF file per day, and emits a Kafka
event with the file manifest.

Two datasets supported:
    era5-land   (default)  0.1° resolution, ~5-day latency, all 8 variables
    era5                    0.25° resolution, ~24h latency, NO soil variables
                            (soil_temp, soil_water will be missing)

Variables requested:
    temperature_2m_max, temperature_2m_min  → derived from 2m_temperature
    u_component_of_wind_10m                 → 10m_u_component_of_wind
    v_component_of_wind_10m                 → 10m_v_component_of_wind
    dewpoint_temperature_2m                 → 2m_dewpoint_temperature
    soil_temperature_level_1                → NOT in ERA5
    surface_solar_radiation_downwards_sum
    surface_pressure
    volumetric_soil_water_layer_1           → NOT in ERA5

Usage:
    python era5land_producer.py --days 7                          # ERA5-Land
    python era5land_producer.py --days 7 --dataset era5           # near-real-time ERA5
    python era5land_producer.py --start 2026-06-10 --end 2026-06-16
    python era5land_producer.py --days 7 --no-kafka

Environment:
    CDSAPI_URL      — CDS API endpoint
    CDSAPI_KEY      — CDS API key (UID:API_KEY)
    KAFKA_BROKER    — bootstrap server (default: localhost:9092)
    KAFKA_TOPIC     — topic name (default: era5land-raw-data)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import cdsapi
from confluent_kafka import Producer

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "era5land"
RAW_DIR.mkdir(parents=True, exist_ok=True)

MOROCCO_BBOX = [36, -17, 27, -1]  # N, W, S, E

# CDS ERA5-Land hourly variable names
ERA5LAND_VARS_CDS = [
    "2m_temperature",
    "2m_dewpoint_temperature",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "surface_pressure",
    "soil_temperature_level_1",
    "surface_solar_radiation_downwards",
    "volumetric_soil_water_layer_1",
]

# ERA5 (non-Land) lacks soil variables — subset of the above
ERA5_VARS_CDS = [
    "2m_temperature",
    "2m_dewpoint_temperature",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "surface_pressure",
    "surface_solar_radiation_downwards",
]

# Dataset CDS IDs and latencies
DATASETS = {
    "era5-land": {"cds_id": "reanalysis-era5-land", "latency_days": 5},
    "era5":      {"cds_id": "reanalysis-era5-single-levels", "latency_days": 5},
}

# Friendly / user-facing channel names
CHANNELS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "u_component_of_wind_10m",
    "v_component_of_wind_10m",
    "dewpoint_temperature_2m",
    "soil_temperature_level_1",
    "surface_solar_radiation_downwards_sum",
    "surface_pressure",
    "volumetric_soil_water_layer_1",
]

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC_ERA5LAND", "era5land-raw-data")

MAX_RETRIES = 3
RETRY_DELAY_S = 30

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("ERA5L-Producer")


# ---------------------------------------------------------------------------
# Kafka helpers
# ---------------------------------------------------------------------------
def _delivery_report(err: object, msg: object) -> None:
    if err is not None:
        logger.error("Kafka delivery failed: %s", err)
    else:
        logger.info("Delivered to %s [%d] @ offset %d", msg.topic(), msg.partition(), msg.offset())


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------
def _date_range(start: Optional[str], end: Optional[str], days_back: int, latency_days: int) -> Tuple[str, str]:
    """Account for dataset latency (ERA5-Land ~5d, ERA5 ~1d)."""
    if end is None:
        end_date = (datetime.now(timezone.utc).date() - timedelta(days=latency_days))
    else:
        end_date = datetime.strptime(end, "%Y-%m-%d").date()

    if start is not None:
        start_date = datetime.strptime(start, "%Y-%m-%d").date()
    else:
        start_date = end_date - timedelta(days=days_back - 1)

    return start_date.isoformat(), end_date.isoformat()


def _days_list(start: str, end: str) -> List[str]:
    s = datetime.strptime(start, "%Y-%m-%d").date()
    e = datetime.strptime(end, "%Y-%m-%d").date()
    return [(s + timedelta(days=i)).isoformat() for i in range((e - s).days + 1)]


# ---------------------------------------------------------------------------
# CDS download
# ---------------------------------------------------------------------------
def _download_day(date_str: str, out_path: Path, dataset: str) -> Path:
    """Download a single day of hourly data for Morocco.

    CDS returns a ZIP archive containing the NetCDF file — extracted to *out_path*.
    """
    if out_path.exists() and out_path.stat().st_size > 1024:
        logger.info("Skip existing %s", out_path.name)
        return out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)
    ds_info = DATASETS[dataset]
    variables = ERA5_VARS_CDS if dataset == "era5" else ERA5LAND_VARS_CDS

    logger.info("Requesting %s for %s [%s variables]", ds_info["cds_id"], date_str, len(variables))

    request = {
        "product_type": ["reanalysis"],
        "data_format": "netcdf",
        "variable": variables,
        "year": date_str[:4],
        "month": date_str[5:7],
        "day": date_str[8:10],
        "time": [f"{h:02d}:00" for h in range(24)],
        "area": MOROCCO_BBOX,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = cdsapi.Client()
            zip_path = out_path.with_suffix(".zip")
            client.retrieve(ds_info["cds_id"], request, str(zip_path))

            # Extract the .nc file from the zip archive
            with zipfile.ZipFile(zip_path, "r") as zf:
                nc_names = [n for n in zf.namelist() if n.endswith(".nc")]
                if not nc_names:
                    raise RuntimeError(f"No .nc file found in {zip_path}")
                zf.extract(nc_names[0], path=out_path.parent)
                extracted = out_path.parent / nc_names[0]
                if extracted != out_path:
                    extracted.rename(out_path)
            zip_path.unlink(missing_ok=True)

            size_mb = out_path.stat().st_size / 1e6
            logger.info("Saved %s (%.1f MB)", out_path.name, size_mb)
            return out_path
        except Exception:
            logger.exception("CDS download attempt %d/%d failed for %s", attempt, MAX_RETRIES, date_str)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_S)
            # Clean up partial downloads
            for p in (out_path, out_path.with_suffix(".zip")):
                p.unlink(missing_ok=True)

    raise RuntimeError(f"CDS download failed after {MAX_RETRIES} attempts for {date_str}")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def run(
    days_back: int = 7,
    start: Optional[str] = None,
    end: Optional[str] = None,
    no_kafka: bool = False,
    dataset: str = "era5-land",
) -> None:
    ds_info = DATASETS[dataset]
    start_date, end_date = _date_range(start, end, days_back, ds_info["latency_days"])
    days = _days_list(start_date, end_date)

    prefix = dataset.replace("-", "")
    logger.info("START %s Ingestion | window: %s → %s (%d days)", dataset, start_date, end_date, len(days))

    files: List[str] = []
    for day in days:
        date_slug = day.replace("-", "")
        out_path = RAW_DIR / f"{prefix}_{date_slug}.nc"
        downloaded = _download_day(day, out_path, dataset)
        files.append(str(downloaded.resolve()))

    message = {
        "event": f"new_{prefix}_data",
        "dataset": dataset,
        "start_date": start_date,
        "end_date": end_date,
        "days_count": len(days),
        "variables": CHANNELS,
        "cds_variables": variables if 'variables' in dir() else ERA5LAND_VARS_CDS,
        "bbox": MOROCCO_BBOX,
        "files": files,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    if not no_kafka:
        producer = Producer({"bootstrap.servers": KAFKA_BROKER})
        try:
            producer.produce(
                KAFKA_TOPIC,
                key=f"morocco_{prefix}",
                value=json.dumps(message, indent=2),
                callback=_delivery_report,
            )
            producer.flush(timeout=30)
        except Exception:
            logger.exception("Failed to produce Kafka message")
            raise
        finally:
            producer.purge()
    else:
        logger.info("Skipping Kafka (--no-kafka). Payload: %s", json.dumps(message, indent=2))

    logger.info("%s ingestion completed — %d files", dataset, len(files))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ERA5 / ERA5-Land Hourly Data Ingestion (Morocco)")
    parser.add_argument("--days", type=int, default=7, help="Number of full days to download (default: 7)")
    parser.add_argument("--start", type=str, default=None, help="Start date YYYY-MM-DD (overrides --days)")
    parser.add_argument("--end", type=str, default=None, help="End date YYYY-MM-DD (default: auto)")
    parser.add_argument("--no-kafka", action="store_true", help="Skip Kafka message production")
    parser.add_argument(
        "--dataset",
        choices=["era5-land", "era5"],
        default="era5-land",
        help="era5-land: 0.1°, 8 vars, ~5d latency | era5: 0.25°, 6 vars (no soil), ~24h latency",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    try:
        run(days_back=args.days, start=args.start, end=args.end, no_kafka=args.no_kafka, dataset=args.dataset)
    except Exception:
        logger.exception("Fatal error during ERA5 ingestion")
        sys.exit(1)