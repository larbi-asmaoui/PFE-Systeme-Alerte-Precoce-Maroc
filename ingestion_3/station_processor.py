"""
Station processor (ingestion_3): merge NASA POWER surface + NOAA Z500/T850.

Joins, per station and per date, the surface CSV (`data/raw/nasa_power/`) with the
upper-air CSV (`data/raw/upperair/`) and writes the training-ready dataset to
`data/processed/stations/<station>.csv`, plus one combined Parquet
(`data/processed/stations_merged.parquet`) for fast notebook loading.

By default it discovers raw files on disk (pure batch). With `--from-kafka` it
instead consumes the producers' manifest topics to learn which files to merge —
the same decoupled pattern as the gfs / era5land processors.

Usage:
    python station_processor.py --no-kafka
    python station_processor.py --from-kafka            # consume manifests, then merge

Environment:
    KAFKA_BROKER, KAFKA_TOPIC_NASA, KAFKA_TOPIC_UPPERAIR, KAFKA_GROUP
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from stations import STATIONS, slug

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
NASA_DIR = PROJECT_ROOT / "data" / "raw" / "nasa_power"
UPPER_DIR = PROJECT_ROOT / "data" / "raw" / "upperair"
OUT_DIR = PROJECT_ROOT / "data" / "processed" / "stations"
COMBINED = PROJECT_ROOT / "data" / "processed" / "stations_merged.parquet"

UPPER_COLS = ["z_500hPa", "t_850hPa"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("Station-Processor")


def _drain_manifests() -> None:
    """Optional: consume both manifest topics so the merge waits for producers."""
    from confluent_kafka import Consumer

    broker = os.getenv("KAFKA_BROKER", "localhost:9092")
    topics = [os.getenv("KAFKA_TOPIC_NASA", "nasa-power-raw"),
              os.getenv("KAFKA_TOPIC_UPPERAIR", "upperair-raw")]
    consumer = Consumer({
        "bootstrap.servers": broker,
        "group.id": os.getenv("KAFKA_GROUP", "ingestion3-processor"),
        "auto.offset.reset": "earliest",
    })
    consumer.subscribe(topics)
    logger.info("Consuming manifests from %s ...", topics)
    seen, idle = 0, 0
    try:
        while idle < 5:                      # stop after ~5s with no new messages
            msg = consumer.poll(1.0)
            if msg is None:
                idle += 1
                continue
            if msg.error():
                logger.warning("kafka error: %s", msg.error())
                continue
            idle = 0
            seen += 1
            m = json.loads(msg.value())
            logger.info("manifest: %s/%s rows=%s", m.get("source"), m.get("station"), m.get("rows"))
    finally:
        consumer.close()
    logger.info("Drained %d manifests.", seen)


def _merge_station(name: str) -> Optional[pd.DataFrame]:
    nasa_path = NASA_DIR / f"{slug(name)}.csv"
    upper_path = UPPER_DIR / f"{slug(name)}_upperair.csv"
    if not nasa_path.exists():
        logger.warning("  no surface file for %s — skipped", name)
        return None

    surface = pd.read_csv(nasa_path, parse_dates=["date"])
    if upper_path.exists():
        upper = pd.read_csv(upper_path, parse_dates=["date"]).drop_duplicates("date")
        merged = surface.merge(upper[["date", *UPPER_COLS]], on="date", how="left")
        # Synoptic fields are smooth — fill the gaps where upper-air years are missing.
        merged[UPPER_COLS] = (merged[UPPER_COLS]
                              .interpolate(method="linear", limit_direction="both"))
        cover = merged[UPPER_COLS].notna().all(axis=1).mean() * 100
        logger.info("  %s: %d rows | upper-air coverage %.1f%%", name, len(merged), cover)
    else:
        merged = surface.copy()
        for c in UPPER_COLS:
            merged[c] = pd.NA
        logger.warning("  %s: no upper-air file — z500/t850 left empty", name)

    merged.insert(0, "station", slug(name))
    return merged


def main() -> None:
    ap = argparse.ArgumentParser(description="Merge NASA POWER + Z500/T850 per station")
    ap.add_argument("--from-kafka", action="store_true", help="consume manifest topics first")
    ap.add_argument("--no-kafka", action="store_true", help="filesystem discovery only (default)")
    args = ap.parse_args()

    if args.from_kafka and not args.no_kafka:
        try:
            _drain_manifests()
        except Exception:
            logger.exception("Kafka consume failed; falling back to filesystem discovery.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    frames: List[pd.DataFrame] = []
    for st in STATIONS:
        df = _merge_station(str(st["station"]))
        if df is None:
            continue
        df.to_csv(OUT_DIR / f"{slug(str(st['station']))}.csv", index=False)
        frames.append(df)

    if frames:
        combined = pd.concat(frames, ignore_index=True)
        try:
            combined.to_parquet(COMBINED, index=False)
            logger.info("Wrote %s (%d rows, %d stations)", COMBINED, len(combined), len(frames))
        except Exception:
            logger.exception("Parquet write failed (install pyarrow); per-station CSVs are fine.")
    logger.info("Done: %d/%d stations merged -> %s", len(frames), len(STATIONS), OUT_DIR)


if __name__ == "__main__":
    main()
