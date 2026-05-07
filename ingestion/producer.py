"""
Live Data Ingestion — downloads the last 7 days of ERA5 data via CDS API
and publishes file-path metadata to Kafka.

Designed to run daily (cron / Airflow / K8s CronJob).

Reference grid: Morocco bounding-box  [36, -17, 27, -1]  →  37 lat x 65 lon at 0.25°
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple

import cdsapi
from confluent_kafka import Producer

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SURFACE_DATASET   = "reanalysis-era5-land"
PRESSURE_DATASET  = "reanalysis-era5-pressure-levels"

SURFACE_VARIABLES = [
    "2m_temperature",
    "2m_dewpoint_temperature",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
]

PRESSURE_VARIABLES = ["geopotential", "temperature"]
PRESSURE_LEVELS    = ["500", "850"]
PRESSURE_TIMES     = ["12:00"]

# Morocco bounding box  [N, W, S, E]  →  CDS convention: [North, West, South, East]
BOUNDING_BOX = [36, -17, 27, -1]

MAX_RETRIES    = 3
RETRY_DELAY_S  = 60

KAFKA_BROKER  = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC   = os.getenv("KAFKA_TOPIC", "era5-raw-data")

CURRENT_DIR   = Path(__file__).resolve().parent
PROJECT_ROOT  = CURRENT_DIR.parent
RAW_DIR       = PROJECT_ROOT / "data" / "raw" / "live"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ERA5-Ingestion")

# ---------------------------------------------------------------------------
# Kafka helper
# ---------------------------------------------------------------------------
def _delivery_report(err: object, msg: object) -> None:
    if err is not None:
        logger.error("Kafka delivery failed: %s", err)
    else:
        logger.info(
            "Delivered to %s [%d] @ offset %d",
            msg.topic(),          # type: ignore[union-attr]
            msg.partition(),      # type: ignore[union-attr]
            msg.offset(),         # type: ignore[union-attr]
        )


# ---------------------------------------------------------------------------
# CDS download helpers
# ---------------------------------------------------------------------------
def _build_client() -> cdsapi.Client:
    """Build CDS API client.  Reads ~/.cdsapirc automatically."""
    return cdsapi.Client(quiet=False)


def _date_range(days_back: int = 7) -> Tuple[str, str]:
    """Return (start_date, end_date) as YYYY-MM-DD covering *last* `days_back` days."""
    end = datetime.utcnow() - timedelta(days=5)
    start = end - timedelta(days=days_back - 1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _days_list(start: str, end: str) -> list[str]:
    """Expand inclusive date range to a list of YYYY-MM-DD strings."""
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d")
    return [(s + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((e - s).days + 1)]


def _download_surface(client: cdsapi.Client, days: list[str], out_path: Path) -> None:
    req = {
        "variable": SURFACE_VARIABLES,
        "year":     sorted(set(d.split("-")[0] for d in days)),
        "month":    sorted(set(d.split("-")[1] for d in days)),
        "day":      sorted(set(d.split("-")[2] for d in days)),
        "time":     [f"{h:02d}:00" for h in range(24)],
        "area":     BOUNDING_BOX,
        "format":   "netcdf",
        "data_format": "netcdf",
        "download_format": "unarchived",
    }
    logger.info(
        "Surface request -> %s … %s  (%d days)",
        days[0], days[-1], len(days),
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client.retrieve(SURFACE_DATASET, req, str(out_path))
            size_mb = out_path.stat().st_size / 1e6
            logger.info("Surface saved: %s  (%.1f MB)", out_path.name, size_mb)
            return
        except Exception:
            logger.exception("Surface download attempt %d/%d failed", attempt, MAX_RETRIES)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_S)
    raise RuntimeError(f"Surface download exhausted retries for {out_path.name}")


def _download_pressure(client: cdsapi.Client, days: list[str], out_path: Path) -> None:
    req = {
        "product_type":   "reanalysis",
        "variable":       PRESSURE_VARIABLES,
        "pressure_level": PRESSURE_LEVELS,
        "year":           sorted(set(d.split("-")[0] for d in days)),
        "month":          sorted(set(d.split("-")[1] for d in days)),
        "day":            sorted(set(d.split("-")[2] for d in days)),
        "time":           PRESSURE_TIMES,
        "area":           BOUNDING_BOX,
        "format":         "netcdf",
        "data_format":    "netcdf",
        "download_format": "unarchived",
    }
    logger.info(
        "Pressure request -> %s … %s  (12:00 UTC snapshots)",
        days[0], days[-1],
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client.retrieve(PRESSURE_DATASET, req, str(out_path))
            size_mb = out_path.stat().st_size / 1e6
            logger.info("Pressure saved: %s  (%.1f MB)", out_path.name, size_mb)
            return
        except Exception:
            logger.exception("Pressure download attempt %d/%d failed", attempt, MAX_RETRIES)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_S)
    raise RuntimeError(f"Pressure download exhausted retries for {out_path.name}")


# ---------------------------------------------------------------------------
# Main ingestion pipeline
# ---------------------------------------------------------------------------
def run(days_back: int = 7) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    start_date, end_date = _date_range(days_back)
    days = _days_list(start_date, end_date)
    date_slug = end_date.replace("-", "")

    file_surface  = RAW_DIR / f"era5_live_surface_{date_slug}.nc"
    file_pressure = RAW_DIR / f"era5_live_pressure_{date_slug}.nc"

    client = _build_client()

    logger.info("=" * 60)
    logger.info("START ERA5 Ingestion | window: %s → %s", start_date, end_date)
    logger.info("=" * 60)

    _download_surface(client, days, file_surface)
    _download_pressure(client, days, file_pressure)

    # ---- Kafka message ----
    message = {
        "event":              "new_weather_data",
        "file_path_surface":  str(file_surface.resolve()),
        "file_path_pressure": str(file_pressure.resolve()),
        "start_date":         start_date,
        "end_date":           end_date,
        "days_count":         len(days),
        "bbox":               BOUNDING_BOX,
        "generated_at":       datetime.utcnow().isoformat() + "Z",
    }

    producer = Producer({"bootstrap.servers": KAFKA_BROKER})
    try:
        producer.produce(
            KAFKA_TOPIC,
            key="morocco_live",
            value=json.dumps(message, indent=2),
            callback=_delivery_report,
        )
        producer.flush(timeout=30)
    except Exception:
        logger.exception("Failed to produce Kafka message")
        raise
    finally:
        producer.purge()

    logger.info("Ingestion job completed successfully.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ERA5 Live Data Ingestion for SAP Morocco")
    parser.add_argument(
        "--days", type=int, default=7,
        help="Number of past days to download (default: 7)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    try:
        run(days_back=args.days)
    except Exception:
        logger.exception("Fatal error during ingestion")
        sys.exit(1)
