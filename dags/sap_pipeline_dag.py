"""
SAP Morocco — daily Early Warning System pipeline.

Runs every day at 06:00 (Africa/Casablanca) and chains the three stages of the
MLOps pipeline:

    ingest_era5  ->  wait_for_tensor  ->  run_inference

  1. ingest_era5      BashOperator   — runs ingestion/producer.py: downloads the
                                       last 7 days of ERA5, archives the raw NetCDF
                                       files to MinIO and emits a Kafka event.
  2. wait_for_tensor  PythonSensor   — polls MinIO until Spark has written a fresh
                                       `tensors/tensor_live_*.npy` for this run.
  3. run_inference    BashOperator   — runs backend/predictor.py: pulls the tensor,
                                       runs the PyTorch model, archives the raw
                                       prediction to MinIO and writes the alerts
                                       GeoJSON / PostGIS rows for FastAPI.

Spark Structured Streaming runs as a long-lived service (sap_spark_processor) and
reacts to the Kafka event between steps 1 and 2; the sensor is what synchronises
the otherwise-decoupled streaming stage back into the batch DAG.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.sensors.python import PythonSensor

# Make the mounted backend package importable so we can reuse the S3 helper.
sys.path.insert(0, "/opt/airflow/backend")

logger = logging.getLogger("sap.dag")

# Container paths (see docker-compose volume mounts on the Airflow services)
INGESTION_DIR = "/opt/airflow/ingestion"
BACKEND_DIR = "/opt/airflow/backend"

DEFAULT_ARGS = {
    "owner": "sap-mlops",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "depends_on_past": False,
}


def _wait_for_tensor(**context) -> bool:
    """
    Poke MinIO for a fresh Spark tensor.

    Returns True once a `tensors/*.npy` object exists that was last modified
    after this DAG run started — i.e. produced by the current ingestion step,
    not a stale leftover from a previous day.
    """
    from app.core.storage import TENSOR_PREFIX, get_storage

    storage = get_storage()
    if storage is None:
        logger.warning("MinIO not reachable yet — will retry")
        return False

    latest = storage.latest_object(TENSOR_PREFIX, suffix=".npy")
    if latest is None:
        logger.info("No tensor in MinIO under '%s' yet", TENSOR_PREFIX)
        return False

    run_start = context["data_interval_start"]
    # Airflow passes a pendulum datetime (tz-aware); compare against S3 LastModified.
    last_modified = latest["LastModified"]
    if last_modified.tzinfo is None:
        last_modified = last_modified.replace(tzinfo=timezone.utc)

    if last_modified >= run_start:
        logger.info("Fresh tensor ready: %s (modified %s)", latest["Key"], last_modified)
        return True

    logger.info(
        "Latest tensor %s is stale (modified %s < run start %s) — waiting",
        latest["Key"], last_modified, run_start,
    )
    return False


with DAG(
    dag_id="sap_pipeline",
    description="Daily Early Warning System pipeline for Morocco (ERA5 -> Spark -> PyTorch)",
    schedule="0 6 * * *",
    start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["sap", "morocco", "mlops", "heatwave"],
) as dag:

    # ---- Task 1: ingestion ----
    ingest_era5 = BashOperator(
        task_id="ingest_era5",
        bash_command=f"cd {INGESTION_DIR} && python producer.py --days 7",
    )

    # ---- Task 2: wait for the Spark tensor to land in MinIO ----
    wait_for_tensor = PythonSensor(
        task_id="wait_for_tensor",
        python_callable=_wait_for_tensor,
        poke_interval=60,          # check once a minute
        timeout=60 * 60,           # give Spark up to an hour
        mode="reschedule",         # free the worker slot between pokes
        soft_fail=False,
    )

    # ---- Task 3: PyTorch inference + post-processing ----
    run_inference = BashOperator(
        task_id="run_inference",
        bash_command=f"cd {BACKEND_DIR} && python predictor.py",
    )

    ingest_era5 >> wait_for_tensor >> run_inference
