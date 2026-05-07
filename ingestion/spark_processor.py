"""
PySpark Structured Streaming processor for ERA5 live weather data.

Listens to 'era5-raw-data' Kafka topic, opens NetCDF files with xarray,
interpolates pressure grids to surface resolution, aggregates hourly data
to daily metrics, extracts the 7 standard channels, applies Z-Score
normalisation using training statistics, and writes `.npy` tensors ready
for PyTorch inference.

Channel order (hard requirement for the ConvLSTM model):
    ['tmax', 'tmin', 'rh', 'u10', 'v10', 'z500', 't850']
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import xarray as xr
from pyspark.sql import DataFrame, SparkSession

# ---------------------------------------------------------------------------
# Paths  (relative to spark_processor.py →  PROJECT_ROOT)
# ---------------------------------------------------------------------------
CURRENT_DIR  = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent

STATS_PATH   = PROJECT_ROOT / "backend" / "artifacts" / "normalization.npz"
READY_DIR    = PROJECT_ROOT / "data" / "ready_for_inference"

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
logger = logging.getLogger("Spark-Processor")


# ---------------------------------------------------------------------------
# NetCDF processing  (mirrors Data-collector-pfe/processor.py)
# ---------------------------------------------------------------------------
def _normalise_time(ds: xr.Dataset) -> xr.Dataset:
    if "valid_time" in ds.coords and "time" not in ds.dims:
        ds = ds.rename({"valid_time": "time"})
    return ds


def _create_daily_features(
    ds_surf: xr.Dataset, ds_pres: xr.Dataset, interpolation: str = "linear"
) -> xr.Dataset:
    """
    Derive 7 daily-aggregated channels from hourly surface & synoptic pressure data.

    0: tmax  — daily maximum 2m temperature (C)
    1: tmin  — daily minimum 2m temperature (C)
    2: rh    — daily mean relative humidity via Magnus  (0-100 %)
    3: u10   — daily mean 10m eastward wind    (m/s)
    4: v10   — daily mean 10m northward wind   (m/s)
    5: z500  — daily mean geopotential @ 500 hPa (m²/s²)
    6: t850  — daily mean temperature  @ 850 hPa (K)
    """
    # ---- surface ----
    t_c = ds_surf["t2m"] - 273.15
    tmax = t_c.resample(time="1D").max()
    tmin = t_c.resample(time="1D").min()

    td_c = ds_surf["d2m"] - 273.15
    rh = 100.0 * (
        np.exp((17.625 * td_c) / (243.04 + td_c))
        / np.exp((17.625 * t_c)  / (243.04 + t_c))
    )
    rh_day = rh.resample(time="1D").mean()

    u10_day = ds_surf["u10"].resample(time="1D").mean()
    v10_day = ds_surf["v10"].resample(time="1D").mean()

    # ---- pressure (regrid to surface grid first) ----
    ds_pres_aligned = ds_pres.interp(
        latitude=ds_surf.latitude,
        longitude=ds_surf.longitude,
        method=interpolation,
    )

    z500 = (
        ds_pres_aligned["z"]
        .sel(pressure_level=500)
        .drop_vars("pressure_level")
        .resample(time="1D").mean()
    )
    t850 = (
        ds_pres_aligned["t"]
        .sel(pressure_level=850)
        .drop_vars("pressure_level")
        .resample(time="1D").mean()
    )

    ds_daily = xr.Dataset({
        "tmax": tmax,
        "tmin": tmin,
        "rh":   rh_day,
        "u10":  u10_day,
        "v10":  v10_day,
        "z500": z500,
        "t850": t850,
    })
    return ds_daily


# ---------------------------------------------------------------------------
# Spark micro-batch callback
# ---------------------------------------------------------------------------
def _load_normalisation_stats() -> tuple[np.ndarray, np.ndarray]:
    """Return (mean, std) broadcast arrays of shape (7,)."""
    if STATS_PATH.exists():
        stats = np.load(STATS_PATH, allow_pickle=True)
        mean = stats["mean"].astype(np.float32)
        std  = stats["std"].astype(np.float32)
        std  = np.where(std < 1e-6, 1.0, std)
        logger.info("Loaded normalisation stats from %s", STATS_PATH)
        return mean, std

    logger.warning(
        "%s not found — using identity normalisation (mean=0, std=1). "
        "Predictions will be wrong.",
        STATS_PATH,
    )
    mean = np.zeros(7, dtype=np.float32)
    std  = np.ones(7, dtype=np.float32)
    return mean, std


def process_netcdf_batch(df: DataFrame, epoch_id: int) -> None:
    """
    forEachBatch callback — called once per micro-batch.
    Reads Kafka messages, opens NetCDFs, builds tensor, saves .npy.
    """
    rows = df.selectExpr("CAST(value AS STRING)").collect()
    if not rows:
        return

    mean, std = _load_normalisation_stats()

    for row in rows:
        payload: dict
        try:
            payload = json.loads(row["value"])          # type: ignore[index]
        except (json.JSONDecodeError, TypeError):
            logger.warning("Skipping malformed Kafka message")
            continue

        file_surface  = payload.get("file_path_surface")
        file_pressure = payload.get("file_path_pressure")
        end_date      = payload.get("end_date")

        if not file_surface or not file_pressure or not end_date:
            logger.error("Incomplete payload — missing file paths or end_date. Skipping.")
            continue

        logger.info("Processing window ending %s  (epoch %d)", end_date, epoch_id)

        ds_surface: Optional[xr.Dataset] = None
        ds_pressure: Optional[xr.Dataset] = None

        try:
            ds_surface  = _normalise_time(xr.open_dataset(file_surface, engine="netcdf4"))
            ds_pressure = _normalise_time(xr.open_dataset(file_pressure, engine="netcdf4"))

            ds_daily = _create_daily_features(ds_surface, ds_pressure)
            ds_daily = ds_daily.transpose("time", "latitude", "longitude")

            # Build tensor:  [T, lat, lon, C]
            live_tensor = np.stack(
                [ds_daily[ch].values for ch in CHANNELS], axis=-1
            ).astype(np.float32)

            logger.info("Raw tensor shape: %s", live_tensor.shape)

            # Z-Score normalisation  (per-channel broadcast)
            live_tensor_norm = (live_tensor - mean) / std

            date_slug = end_date.replace("-", "")
            out_path = READY_DIR / f"tensor_live_{date_slug}.npy"
            np.save(str(out_path), live_tensor_norm)

            logger.info(
                "Saved %s  |  shape=%s  |  days=%d",
                out_path.name, live_tensor_norm.shape, live_tensor_norm.shape[0],
            )

        except FileNotFoundError:
            logger.exception("NetCDF file not found — may have been cleaned up")
        except KeyError as ke:
            logger.exception("Missing variable in NetCDF: %s", ke)
        except Exception:
            logger.exception("Unexpected error processing batch for %s", end_date)
        finally:
            if ds_surface is not None:
                ds_surface.close()
            if ds_pressure is not None:
                ds_pressure.close()
            if "ds_daily" in locals():
                ds_daily.close()                        # type: ignore[possibly-used-while-undefined?]


# ---------------------------------------------------------------------------
# Streaming application entry point
# ---------------------------------------------------------------------------
def start_streaming(
    broker: str = "localhost:9092",
    topic: str = "era5-raw-data",
    trigger_interval: str = "30 seconds",
) -> None:
    spark = (
        SparkSession.builder
        .appName("ERA5-Weather-Processor")
        .config(
            "spark.jars.packages",
            "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0",
        )
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    logger.info("Listening on Kafka topic '%s' @ %s", topic, broker)

    df_kafka = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", broker)
        .option("subscribe", topic)
        .option("startingOffsets", "latest")
        .option("failOnDataLoss", "false")
        .load()
    )

    query = (
        df_kafka.writeStream
        .foreachBatch(process_netcdf_batch)
        .trigger(processingTime=trigger_interval)
        .option("checkpointLocation", str(PROJECT_ROOT / "data" / "checkpoints" / "spark_streaming"))
        .start()
    )

    logger.info("Streaming query started — awaiting data …")
    query.awaitTermination()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Spark ERA5 Streaming Processor")
    p.add_argument("--broker", default=os.getenv("KAFKA_BROKER", "localhost:9092"))
    p.add_argument("--topic",  default=os.getenv("KAFKA_TOPIC", "era5-raw-data"))
    p.add_argument("--trigger", default="30 seconds")
    args = p.parse_args()

    try:
        start_streaming(args.broker, args.topic, args.trigger)
    except KeyboardInterrupt:
        logger.info("Shutting down by user request")
    except Exception:
        logger.exception("Fatal streaming error")
        sys.exit(1)
