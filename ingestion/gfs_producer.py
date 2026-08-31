"""
GFS ingestion producer (analysis only, f000).
Downloads last 7 full days (UTC) and publishes file list to Kafka.
Supports NOMADS subregion or AWS full-file download.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Tuple

import requests
from confluent_kafka import Producer

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CYCLES = ["00", "06", "12", "18"]
BOUNDING_BOX = [36, -17, 27, -1]

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC_GFS", "gfs-raw-data")

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "gfs"

MAX_RETRIES = 3
RETRY_DELAY_S = 30
MIN_BYTES = 1024
GFS_SOURCE = os.getenv("GFS_SOURCE", "auto")  # auto|nomads|aws

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("GFS-Producer")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _delivery_report(err: object, msg: object) -> None:
    if err is not None:
        logger.error("Kafka delivery failed: %s", err)
    else:
        logger.info(
            "Delivered to %s [%d] @ offset %d",
            msg.topic(),
            msg.partition(),
            msg.offset(),
        )


def _date_range(days_back: int = 7) -> Tuple[str, str]:
    """Return start/end (YYYY-MM-DD) for last 7 full days (UTC)."""
    end = (datetime.utcnow().date() - timedelta(days=1))
    start = end - timedelta(days=days_back - 1)
    return start.isoformat(), end.isoformat()


def _days_list(start: str, end: str) -> List[str]:
    s = datetime.strptime(start, "%Y-%m-%d").date()
    e = datetime.strptime(end, "%Y-%m-%d").date()
    return [(s + timedelta(days=i)).isoformat() for i in range((e - s).days + 1)]


def _build_nomads_url(date: str, cycle: str) -> str:
    base = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
    params = {
        "file": f"gfs.t{cycle}z.pgrb2.0p25.f000",
        "lev_2_m_above_ground": "on",
        "lev_10_m_above_ground": "on",
        "lev_500_mb": "on",
        "lev_850_mb": "on",
        "var_TMP": "on",
        "var_DPT": "on",
        "var_UGRD": "on",
        "var_VGRD": "on",
        "var_HGT": "on",
        "subregion": "",
        "leftlon": str(BOUNDING_BOX[1]),
        "rightlon": str(BOUNDING_BOX[3]),
        "toplat": str(BOUNDING_BOX[0]),
        "bottomlat": str(BOUNDING_BOX[2]),
        "dir": f"/gfs.{date.replace('-', '')}/{cycle}/atmos",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{base}?{query}"


def _build_aws_url(date: str, cycle: str) -> str:
    date_slug = date.replace("-", "")
    return (
        "https://noaa-gfs-bdp-pds.s3.amazonaws.com/"
        f"gfs.{date_slug}/{cycle}/atmos/gfs.t{cycle}z.pgrb2.0p25.f000"
    )


def _download(url: str, out_path: Path, label: str) -> None:
    if out_path.exists():
        if out_path.stat().st_size >= MIN_BYTES:
            logger.info("Skip existing %s", out_path.name)
            return
        out_path.unlink(missing_ok=True)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with requests.get(url, stream=True, timeout=180) as resp:
                resp.raise_for_status()
                content_type = resp.headers.get("Content-Type", "")
                snippet = b""
                total_bytes = 0
                with open(out_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            if not snippet:
                                snippet = chunk[:200]
                            f.write(chunk)
                            total_bytes += len(chunk)
            if total_bytes < MIN_BYTES:
                out_path.unlink(missing_ok=True)
                logger.error(
                    "Empty or tiny response for %s (%s, bytes=%d, content-type=%s). Snippet: %r",
                    out_path.name,
                    label,
                    total_bytes,
                    content_type,
                    snippet,
                )
                raise RuntimeError("Downloaded file too small")
            size_mb = out_path.stat().st_size / 1e6
            logger.info("Saved %s (%.1f MB) [%s]", out_path.name, size_mb, label)
            return
        except Exception:
            logger.exception("Download attempt %d/%d failed", attempt, MAX_RETRIES)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_S)
    raise RuntimeError(f"Download failed: {out_path}")


def _download_with_source(date: str, cycle: str, out_path: Path, source: str) -> str:
    if source not in {"auto", "nomads", "aws"}:
        raise ValueError(f"Unknown source: {source}")

    if source in {"nomads", "auto"}:
        url = _build_nomads_url(date, cycle)
        try:
            _download(url, out_path, "nomads")
            return "nomads"
        except Exception:
            if source == "nomads":
                raise
            logger.warning("NOMADS failed for %s %s, trying AWS...", date, cycle)

    url = _build_aws_url(date, cycle)
    _download(url, out_path, "aws")
    return "aws"


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def run(days_back: int = 7, source: str = "auto", no_kafka: bool = False) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    start_date, end_date = _date_range(days_back)
    days = _days_list(start_date, end_date)

    logger.info("START GFS Ingestion | window: %s -> %s", start_date, end_date)

    files: List[str] = []
    sources_used: List[str] = []
    for day in days:
        date_slug = day.replace("-", "")
        for cycle in CYCLES:
            out_path = RAW_DIR / f"gfs_{date_slug}_{cycle}.grb2"
            used = _download_with_source(day, cycle, out_path, source)
            sources_used.append(used)
            files.append(str(out_path.resolve()))

    message = {
        "event": "new_gfs_data",
        "source": source,
        "sources_used": sorted(set(sources_used)),
        "start_date": start_date,
        "end_date": end_date,
        "days_count": len(days),
        "cycles": CYCLES,
        "files": files,
        "bbox": BOUNDING_BOX,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    if not no_kafka:
        producer = Producer({"bootstrap.servers": KAFKA_BROKER})
        try:
            producer.produce(
                KAFKA_TOPIC,
                key="morocco_gfs",
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
        logger.info("Skipping Kafka (--no-kafka). Message: %s", json.dumps(message, indent=2))

    logger.info("GFS ingestion completed successfully.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GFS Live Data Ingestion (analysis f000)")
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of full days to download (default: 7)",
    )
    parser.add_argument(
        "--source",
        choices=["auto", "nomads", "aws"],
        default=GFS_SOURCE,
        help="Download source: auto (default), nomads, aws",
    )
    parser.add_argument(
        "--no-kafka",
        action="store_true",
        help="Skip Kafka message production",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    try:
        run(days_back=args.days, source=args.source, no_kafka=args.no_kafka)
    except Exception:
        logger.exception("Fatal error during GFS ingestion")
        sys.exit(1)
