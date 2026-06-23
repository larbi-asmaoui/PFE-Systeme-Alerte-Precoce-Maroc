"""
ERA5-Land processor: builds a 7-day spatio-temporal tensor from hourly NetCDFs.

Reads daily ERA5-Land NetCDF files (one per day, up to 24 hourly steps),
computes daily aggregates and derived features, coarsens to the training
grid (37×65 at 0.25°), stacks into a tensor [T, H, W, C] and writes both
.npz (physical, for training) and .npy (normalised, for inference).

Matches the exact 13-channel format expected by the training pipeline
(Copy_of_train_benchmark_models_v2.ipynb / ee_engine_asmaoui_.ipynb).

Channel order (13 channels):
    0  Tmax        — daily max 2m_temperature (K → °C)
    1  Tmin        — daily min 2m_temperature (K → °C)
    2  u_wind      — daily mean 10m_u (m/s)
    3  v_wind      — daily mean 10m_v (m/s)
    4  Tdew        — daily mean 2m_dewpoint (K → °C)
    5  SoilT       — daily mean soil_temperature_level_1 (K → °C)
    6  Solar       — daily total ssrd, last cumulated timestep (J/m²)
    7  Press       — daily mean surface_pressure (Pa → hPa)
    8  SoilM       — daily mean volumetric_soil_water_layer_1 (m³/m³)
    9  WindSpeed   — sqrt(u²+v²), daily mean (m/s)
   10  RH          — Magnus formula from Tmean+Tdew, daily mean (%)
   11  HeatIndex   — NOAA Rothfusz from Tmax + RH (°C)
   12  WindChill   — from Tmin + WindSpeed (°C)

Model targets (from training notebook):
    HeatIndex → channel 11,  WindChill → channel 12

Usage:
    python era5land_processor.py --files data/raw/era5land/*.nc --end-date 2025-06-20
    python era5land_processor.py --start 2025-06-14 --end 2025-06-20  (auto-discover)
    python era5land_processor.py --broker localhost:9092  (Kafka consumer mode)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import xarray as xr
from confluent_kafka import Consumer

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "era5land"
READY_DIR = PROJECT_ROOT / "data" / "ready_for_inference"
STATS_PATH = PROJECT_ROOT / "backend" / "artifacts" / "normalization.npz"

READY_DIR.mkdir(parents=True, exist_ok=True)

CDS_VAR_MAP = {
    "2m_temperature": "t2m",
    "2m_dewpoint_temperature": "d2m",
    "10m_u_component_of_wind": "u10",
    "10m_v_component_of_wind": "v10",
    "surface_pressure": "sp",
    "soil_temperature_level_1": "stl1",
    "surface_solar_radiation_downwards": "ssrd",
    "volumetric_soil_water_layer_1": "swvl1",
}

CHANNEL_NAMES = [
    "Tmax",
    "Tmin",
    "u_wind",
    "v_wind",
    "Tdew",
    "SoilT",
    "Solar",
    "Press",
    "SoilM",
    "WindSpeed",
    "RH",
    "HeatIndex",
    "WindChill",
]

N_CHANNELS = len(CHANNEL_NAMES)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("ERA5L-Processor")


def _load_or_build_stats() -> Tuple[np.ndarray, np.ndarray]:
    if STATS_PATH.exists():
        stats = np.load(STATS_PATH, allow_pickle=True)
        mean = stats["mean"].astype(np.float32)
        std = stats["std"].astype(np.float32)
        if len(mean) >= N_CHANNELS:
            mean = mean[:N_CHANNELS]
            std = std[:N_CHANNELS]
        else:
            logger.warning("Existing stats have %d channels, need %d — padding", len(mean), N_CHANNELS)
            mean = np.pad(mean, (0, N_CHANNELS - len(mean)), constant_values=0.0)
            std = np.pad(std, (0, N_CHANNELS - len(std)), constant_values=1.0)
        std = np.where(std < 1e-6, 1.0, std)
        logger.info("Loaded normalisation stats from %s", STATS_PATH)
        return mean, std

    logger.warning("%s not found — using identity normalisation", STATS_PATH)
    return np.zeros(N_CHANNELS, dtype=np.float32), np.ones(N_CHANNELS, dtype=np.float32)


# ---------------------------------------------------------------------------
# Derived feature formulas — exact match with ee_engine_asmaoui_.ipynb cell 23
# ---------------------------------------------------------------------------
def _compute_wind_speed(u10: np.ndarray, v10: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    ws = np.sqrt(u10 ** 2 + v10 ** 2)
    return np.where(valid_mask, ws, 0.0).astype(np.float32)


def _compute_relative_humidity(tmean_c: np.ndarray, tdew_c: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    e_actual = 6.112 * np.exp((17.67 * tdew_c) / (tdew_c + 243.5))
    e_sat = 6.112 * np.exp((17.67 * tmean_c) / (tmean_c + 243.5))
    rh = np.where((valid_mask) & (e_sat > 0), (e_actual / e_sat) * 100.0, 0.0)
    return np.clip(rh, 0.0, 100.0).astype(np.float32)


def _compute_heat_index(tmax_c: np.ndarray, rh: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    tf = tmax_c * 1.8 + 32.0

    hi_simple = 0.5 * (tf + 61.0 + ((tf - 68.0) * 1.2) + (rh * 0.094))

    hi_full = (
        -42.379
        + 2.04901523 * tf
        + 10.14333127 * rh
        - 0.22475541 * tf * rh
        - 0.00683783 * tf ** 2
        - 0.05481717 * rh ** 2
        + 0.00122874 * tf ** 2 * rh
        + 0.00085282 * tf * rh ** 2
        - 0.00000199 * tf ** 2 * rh ** 2
    )

    hi_f = np.where(tf >= 80, hi_full, hi_simple)
    hi_c = (hi_f - 32.0) / 1.8
    return np.where(valid_mask, hi_c, 0.0).astype(np.float32)


def _compute_wind_chill(tmin_c: np.ndarray, wind_speed: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    tf_min = tmin_c * 1.8 + 32.0
    v_mph = wind_speed * 2.23694

    wc_f = 35.74 + 0.6215 * tf_min - 35.75 * (v_mph ** 0.16) + 0.4275 * tf_min * (v_mph ** 0.16)
    wc_f = np.where(v_mph > 3.0, wc_f, tf_min)
    wc_c = (wc_f - 32.0) / 1.8
    return np.where(valid_mask, wc_c, 0.0).astype(np.float32)


# ---------------------------------------------------------------------------
# NetCDF reading & aggregation
# ---------------------------------------------------------------------------
def _open_nc_variable(ds: xr.Dataset, cds_name: str) -> Optional[np.ndarray]:
    """Extract a CDS-named variable, returning None if absent (ERA5 lacks soil vars)."""
    internal = CDS_VAR_MAP[cds_name]
    for candidate in (cds_name, internal):
        if candidate in ds.data_vars:
            return ds[candidate].values
    return None


def _extract_date_from_path(path: Path) -> str:
    """Parse YYYY-MM-DD from filename: era5land_YYYYMMDD.nc or era5_YYYYMMDD.nc."""
    stem = path.stem
    for token in stem.split("_"):
        if len(token) == 8 and token.isdigit():
            return f"{token[:4]}-{token[4:6]}-{token[6:8]}"
    raise ValueError(f"Cannot parse date from filename: {path.name}")


def _fix_lat_lon(arr: np.ndarray, lat: np.ndarray, lon: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    if lat[0] < lat[-1]:
        lat = lat[::-1]
        arr = arr[::-1, ...]
    lon = np.where(lon > 180, lon - 360, lon)
    order = np.argsort(lon)
    lon = lon[order]
    arr = arr[:, order, ...]
    return arr, lat, lon


def _compute_daily_aggregates(ds: xr.Dataset) -> np.ndarray:
    """
    Compute daily aggregates + 4 derived features from hourly data,
    keeping the native 0.1° ERA5-Land resolution.

    Returns array of shape [lat, lon, 13] in physical units.
    """
    t2m = _open_nc_variable(ds, "2m_temperature")                       # [T, lat, lon] K
    d2m = _open_nc_variable(ds, "2m_dewpoint_temperature")              # [T, lat, lon] K
    u10 = _open_nc_variable(ds, "10m_u_component_of_wind")              # [T, lat, lon] m/s
    v10 = _open_nc_variable(ds, "10m_v_component_of_wind")              # [T, lat, lon] m/s
    stl1_raw = _open_nc_variable(ds, "soil_temperature_level_1")
    ssrd = _open_nc_variable(ds, "surface_solar_radiation_downwards")
    sp = _open_nc_variable(ds, "surface_pressure")
    swvl1_raw = _open_nc_variable(ds, "volumetric_soil_water_layer_1")

    # ERA5 (non-Land) lacks soil/solar variables — substitute zeros
    for name, var in [("soil_temperature_level_1", stl1_raw),
                       ("surface_solar_radiation_downwards", ssrd),
                       ("volumetric_soil_water_layer_1", swvl1_raw)]:
        if var is None:
            logger.info("%s missing — using zeros", name)

    if stl1_raw is None:
        stl1_raw = np.zeros_like(t2m)
    if ssrd is None:
        ssrd = np.zeros_like(t2m)
    if swvl1_raw is None:
        swvl1_raw = np.zeros_like(t2m)

    lat = ds["latitude"].values
    lon = ds["longitude"].values

    # Handle < 24h (ERA5-Land has ~5-day latency so the most recent day is partial)
    t_steps = t2m.shape[0]
    if t_steps < 24:
        logger.info("Only %d/24 hourly steps available — using what we have", t_steps)

    # --- Daily aggregates of raw variables ---
    tmax_k = t2m.max(axis=0)      # [lat, lon]
    tmin_k = t2m.min(axis=0)
    u_mean = u10.mean(axis=0)
    v_mean = v10.mean(axis=0)
    tdew_k = d2m.mean(axis=0)
    soil_k = stl1_raw.mean(axis=0)
    solar_sum = np.maximum(ssrd[-1, :, :], 0.0)
    press_hpa = sp.mean(axis=0) / 100.0
    soil_m = swvl1_raw.mean(axis=0)

    # --- Convert K → °C where needed and build valid-pixel mask ---
    tmax_c = tmax_k - 273.15
    tmin_c = tmin_k - 273.15
    tmean_c = (tmax_c + tmin_c) / 2.0
    tdew_c = tdew_k - 273.15
    soil_c = soil_k - 273.15

    valid = (tmax_k > 0.0)
    tmax_c = np.where(valid, tmax_c, 0.0)
    tmin_c = np.where(valid, tmin_c, 0.0)
    tmean_c = np.where(valid, tmean_c, 0.0)
    tdew_c = np.where(valid, tdew_c, 0.0)
    soil_c = np.where(valid, soil_c, 0.0)
    u_mean = np.where(valid, u_mean, 0.0)
    v_mean = np.where(valid, v_mean, 0.0)
    solar_sum = np.where(valid, solar_sum, 0.0)
    press_hpa = np.where(valid, press_hpa, 0.0)
    soil_m = np.where(valid, soil_m, 0.0)

    # --- Derived features (exact match with ee_engine notebook) ---
    wind_speed = _compute_wind_speed(u_mean, v_mean, valid)
    rh = _compute_relative_humidity(tmean_c, tdew_c, valid)
    heat_index = _compute_heat_index(tmax_c, rh, valid)
    wind_chill = _compute_wind_chill(tmin_c, wind_speed, valid)

    channels = [
        tmax_c,
        tmin_c,
        u_mean,
        v_mean,
        tdew_c,
        soil_c,
        solar_sum,
        press_hpa,
        soil_m,
        wind_speed,
        rh,
        heat_index,
        wind_chill,
    ]

    arr_native = np.stack(channels, axis=-1).astype(np.float32)  # [lat, lon, 13]
    return arr_native


# ---------------------------------------------------------------------------
# Tensor builder
# ---------------------------------------------------------------------------
def build_tensor(files: List[str], end_date: str) -> Path:
    daily_map: Dict[str, Path] = {}
    for f in files:
        path = Path(f)
        if not path.exists():
            logger.warning("Missing file: %s", path)
            continue
        date = _extract_date_from_path(path)
        daily_map[date] = path

    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    expected_days = [(end_dt - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]

    missing = [d for d in expected_days if d not in daily_map]
    if missing:
        raise RuntimeError(f"Missing days for 7-day window ending {end_date}: {missing}")

    extra = [d for d in daily_map if d not in expected_days]
    if extra:
        logger.warning("Extra days in files (ignored): %s", extra)

    day_tensors: List[np.ndarray] = []

    for day in expected_days:
        ds = xr.open_dataset(daily_map[day], engine="netcdf4")
        arr = _compute_daily_aggregates(ds)  # [lat, lon, 13] — native 0.1° resolution
        lat = ds["latitude"].values
        lon = ds["longitude"].values
        ds.close()

        arr, lat, lon = _fix_lat_lon(arr, lat, lon)
        day_tensors.append(arr)

    live_tensor = np.stack(day_tensors, axis=0)  # [T, lat, lon, C]  — physical units
    logger.info("Raw tensor: %s", live_tensor.shape)

    date_slug = end_date.replace("-", "")

    # --- valid_mask: True for land pixels (where Tmax > 0, channel index 0) ---
    valid_mask = (live_tensor[0, :, :, 0] > 0.0)  # [lat, lon]

    # --- Save .npz for training pipeline (physical units, matches notebook format) ---
    npz_path = READY_DIR / f"era5land_13features_{date_slug}.npz"
    np.savez_compressed(
        str(npz_path),
        data=live_tensor.astype(np.float32),
        valid_mask=valid_mask,
    )
    logger.info("Saved %s | keys=[data, valid_mask] | data=%s", npz_path.name, live_tensor.shape)

    # --- Save .npy for live inference pipeline (normalised) ---
    mean, std = _load_or_build_stats()
    live_tensor_norm = (live_tensor - mean.reshape(1, 1, 1, -1)) / std.reshape(1, 1, 1, -1)

    date_slug = end_date.replace("-", "")
    npy_path = READY_DIR / f"tensor_live_era5land_{date_slug}.npy"
    np.save(str(npy_path), live_tensor_norm)

    logger.info(
        "Saved %s | shape=%s | range=[%.2f, %.2f] | channels=%s",
        npy_path.name,
        live_tensor_norm.shape,
        live_tensor_norm.min(),
        live_tensor_norm.max(),
        CHANNEL_NAMES,
    )

    return npy_path


# ---------------------------------------------------------------------------
# Kafka consumer
# ---------------------------------------------------------------------------
def run_kafka(broker: str, topic: str, once: bool = False) -> None:
    consumer = Consumer({
        "bootstrap.servers": broker,
        "group.id": "era5land-processor",
        "auto.offset.reset": "latest",
    })
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
def _auto_discover_files(start: str, end: str) -> List[str]:
    """Glob raw/era5land/*.nc and raw/era5/*.nc files matching date range."""
    days = []
    s = datetime.strptime(start, "%Y-%m-%d").date()
    e = datetime.strptime(end, "%Y-%m-%d").date()
    current = s
    prefixes = ["era5land", "era5"]
    while current <= e:
        date_slug = current.strftime("%Y%m%d")
        found = False
        for prefix in prefixes:
            candidate = RAW_DIR / f"{prefix}_{date_slug}.nc"
            if candidate.exists():
                days.append(str(candidate.resolve()))
                found = True
                break
        if not found:
            logger.warning("File not found for %s (tried %s)", current, prefixes)
        current += timedelta(days=1)
    return days


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ERA5-Land Tensor Builder (13 channels)")
    parser.add_argument("--broker", default=os.getenv("KAFKA_BROKER", "localhost:9092"))
    parser.add_argument("--topic", default=os.getenv("KAFKA_TOPIC_ERA5LAND", "era5land-raw-data"))
    parser.add_argument("--once", action="store_true", help="Process one message then exit (Kafka mode)")
    parser.add_argument("--files", nargs="+", help="Explicit list of NetCDF files")
    parser.add_argument("--end-date", help="End date YYYY-MM-DD (required with --files)")
    parser.add_argument("--start", help="Start date YYYY-MM-DD (auto-discover mode)")
    parser.add_argument("--end", help="End date YYYY-MM-DD (auto-discover mode)")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    try:
        if args.files:
            if not args.end_date:
                raise ValueError("--end-date is required when using --files")
            build_tensor(args.files, args.end_date)
        elif args.start and args.end:
            files = _auto_discover_files(args.start, args.end)
            if not files:
                raise FileNotFoundError(f"No NetCDF files found for {args.start} -> {args.end}")
            build_tensor(files, args.end)
        else:
            run_kafka(args.broker, args.topic, once=args.once)
    except Exception:
        logger.exception("Fatal error during ERA5-Land processing")
        sys.exit(1)