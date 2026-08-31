"""
GFS processor: builds 7-day tensor from GFS analysis GRIB2 files.
Consumes Kafka messages (topic: gfs-raw-data) and writes ready_for_inference tensor.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import xarray as xr
from confluent_kafka import Consumer

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent

STATS_PATH = PROJECT_ROOT / "backend" / "artifacts" / "normalization.npz"
READY_DIR = PROJECT_ROOT / "data" / "ready_for_inference"

READY_DIR.mkdir(parents=True, exist_ok=True)

CHANNELS = ["tmax", "tmin", "rh", "u10", "v10", "z500", "t850"]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("GFS-Processor")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_normalisation_stats() -> Tuple[np.ndarray, np.ndarray]:
    if STATS_PATH.exists():
        stats = np.load(STATS_PATH, allow_pickle=True)
        mean = stats["mean"].astype(np.float32)
        std = stats["std"].astype(np.float32)
        std = np.where(std < 1e-6, 1.0, std)
        logger.info("Loaded normalisation stats from %s", STATS_PATH)
        return mean, std

    logger.warning("%s not found — using identity normalisation", STATS_PATH)
    return np.zeros(7, dtype=np.float32), np.ones(7, dtype=np.float32)


def _open_grib_var(
    path: Path,
    short_name: str,
    type_of_level: str | None = None,
    level: int | None = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    keys: Dict[str, object] = {"shortName": short_name}
    if type_of_level is not None:
        keys["typeOfLevel"] = type_of_level
    if level is not None:
        keys["level"] = level

    ds = xr.open_dataset(
        path, engine="cfgrib", backend_kwargs={"filter_by_keys": keys}
    )
    var_name = list(ds.data_vars.keys())[0]
    data = ds[var_name].values
    lat = ds["latitude"].values
    lon = ds["longitude"].values
    ds.close()
    return data, lat, lon


def _read_with_fallback(
    path: Path,
    short_names: Iterable[str],
    type_of_level: str | None = None,
    level: int | None = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    last_err: Exception | None = None
    for name in short_names:
        try:
            return _open_grib_var(path, name, type_of_level, level)
        except Exception as err:
            last_err = err
    raise RuntimeError(f"Failed to read {short_names} from {path}") from last_err


def _rh_from_t_td(t_c: np.ndarray, td_c: np.ndarray) -> np.ndarray:
    rh = 100.0 * (
        np.exp((17.625 * td_c) / (243.04 + td_c))
        / np.exp((17.625 * t_c) / (243.04 + t_c))
    )
    return np.clip(rh, 0.0, 100.0)


def _fix_lat_lon(
    arr: np.ndarray, lat: np.ndarray, lon: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    # Ensure latitude is descending (north -> south)
    if lat[0] < lat[-1]:
        lat = lat[::-1]
        arr = arr[::-1, :]

    # Convert lon to [-180, 180] and sort ascending
    lon = np.where(lon > 180, lon - 360, lon)
    order = np.argsort(lon)
    lon = lon[order]
    arr = arr[:, order]

    return arr, lat, lon


def _parse_date_from_path(path: Path) -> str:
    # gfs_YYYYMMDD_HH.grb2
    stem = path.stem
    parts = stem.split("_")
    if len(parts) < 3:
        raise ValueError(f"Unexpected file name: {path.name}")
    date_slug = parts[1]
    return f"{date_slug[:4]}-{date_slug[4:6]}-{date_slug[6:8]}"


def _expected_days(end_date: str, days_back: int = 7) -> List[str]:
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    start = end - timedelta(days=days_back - 1)
    return [(start + timedelta(days=i)).isoformat() for i in range(days_back)]


def build_tensor(files: List[str], end_date: str) -> Path:
    daily: Dict[str, Dict[str, List[np.ndarray]]] = {}
    lat_ref: np.ndarray | None = None
    lon_ref: np.ndarray | None = None

    for f in files:
        path = Path(f)
        if not path.exists():
            logger.warning("Missing file: %s", path)
            continue

        date = _parse_date_from_path(path)
        daily.setdefault(date, {"t2m": [], "d2m": [], "u10": [], "v10": [], "z500": [], "t850": []})

        t2m, lat, lon = _read_with_fallback(path, ["2t", "t2m"], "heightAboveGround", 2)
        d2m, _, _ = _read_with_fallback(path, ["2d", "d2m"], "heightAboveGround", 2)
        u10, _, _ = _read_with_fallback(path, ["10u", "u10"], "heightAboveGround", 10)
        v10, _, _ = _read_with_fallback(path, ["10v", "v10"], "heightAboveGround", 10)
        z500, _, _ = _read_with_fallback(path, ["gh", "z"], "isobaricInhPa", 500)
        t850, _, _ = _read_with_fallback(path, ["t"], "isobaricInhPa", 850)

        # Fix orientation to match training grid
        t2m, lat, lon = _fix_lat_lon(t2m, lat, lon)
        d2m, _, _ = _fix_lat_lon(d2m, lat, lon)
        u10, _, _ = _fix_lat_lon(u10, lat, lon)
        v10, _, _ = _fix_lat_lon(v10, lat, lon)
        z500, _, _ = _fix_lat_lon(z500, lat, lon)
        t850, _, _ = _fix_lat_lon(t850, lat, lon)

        if lat_ref is None:
            lat_ref, lon_ref = lat, lon

        # Convert units
        t2m_c = t2m - 273.15
        d2m_c = d2m - 273.15

        # Convert geopotential height to geopotential if needed
        if np.nanmean(z500) < 20000:
            z500 = z500 * 9.80665

        daily[date]["t2m"].append(t2m_c)
        daily[date]["d2m"].append(d2m_c)
        daily[date]["u10"].append(u10)
        daily[date]["v10"].append(v10)
        daily[date]["z500"].append(z500)
        daily[date]["t850"].append(t850)

    dates_sorted = sorted(daily.keys())
    if len(dates_sorted) == 0:
        raise RuntimeError("No valid GFS files processed")

    expected_days = _expected_days(end_date, days_back=7)
    missing_days = [d for d in expected_days if d not in daily]
    extra_days = [d for d in dates_sorted if d not in expected_days]

    if missing_days:
        raise RuntimeError(f"Missing days for 7-day window: {missing_days}")
    if extra_days:
        logger.warning("Extra days found (ignoring): %s", extra_days)

    dates_sorted = expected_days

    day_tensors: List[np.ndarray] = []
    for day in dates_sorted:
        t2m_stack = np.stack(daily[day]["t2m"], axis=0)
        d2m_stack = np.stack(daily[day]["d2m"], axis=0)
        u10_stack = np.stack(daily[day]["u10"], axis=0)
        v10_stack = np.stack(daily[day]["v10"], axis=0)
        z500_stack = np.stack(daily[day]["z500"], axis=0)
        t850_stack = np.stack(daily[day]["t850"], axis=0)

        tmax = t2m_stack.max(axis=0)
        tmin = t2m_stack.min(axis=0)
        rh = _rh_from_t_td(t2m_stack, d2m_stack).mean(axis=0)
        u10 = u10_stack.mean(axis=0)
        v10 = v10_stack.mean(axis=0)
        z500 = z500_stack.mean(axis=0)
        t850 = t850_stack.mean(axis=0)

        day_tensor = np.stack([tmax, tmin, rh, u10, v10, z500, t850], axis=-1)
        day_tensors.append(day_tensor.astype(np.float32))

    live_tensor = np.stack(day_tensors, axis=0)  # [T, lat, lon, C]

    mean, std = _load_normalisation_stats()
    live_tensor_norm = (live_tensor - mean) / std

    date_slug = end_date.replace("-", "")
    out_path = READY_DIR / f"tensor_live_{date_slug}.npy"
    np.save(str(out_path), live_tensor_norm)

    logger.info(
        "Saved %s | shape=%s | days=%d",
        out_path.name,
        live_tensor_norm.shape,
        live_tensor_norm.shape[0],
    )

    return out_path


# ---------------------------------------------------------------------------
# Kafka consumer
# ---------------------------------------------------------------------------
def run_kafka(broker: str, topic: str, once: bool = False) -> None:
    consumer = Consumer(
        {
            "bootstrap.servers": broker,
            "group.id": "gfs-processor",
            "auto.offset.reset": "latest",
        }
    )
    consumer.subscribe([topic])

    try:
        while True:
            msg = consumer.poll(timeout=10)
            if msg is None:
                continue
            if msg.error():
                logger.error("Kafka error: %s", msg.error())
                continue

            payload = json.loads(msg.value().decode("utf-8"))
            files = payload.get("files", [])
            end_date = payload.get("end_date")
            if not files or not end_date:
                logger.error("Missing files or end_date in payload")
                continue

            build_tensor(files, end_date)

            if once:
                break
    finally:
        consumer.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GFS Processor")
    parser.add_argument("--broker", default=os.getenv("KAFKA_BROKER", "localhost:9092"))
    parser.add_argument("--topic", default=os.getenv("KAFKA_TOPIC_GFS", "gfs-raw-data"))
    parser.add_argument("--once", action="store_true", help="Process one message then exit")
    parser.add_argument(
        "--files",
        nargs="+",
        help="Optional explicit list of GRIB2 files (bypass Kafka)",
    )
    parser.add_argument(
        "--end-date",
        help="End date YYYY-MM-DD (required when using --files)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    try:
        if args.files:
            if not args.end_date:
                raise ValueError("--end-date is required when using --files")
            build_tensor(args.files, args.end_date)
        else:
            run_kafka(args.broker, args.topic, once=args.once)
    except Exception:
        logger.exception("Fatal error during GFS processing")
        sys.exit(1)
