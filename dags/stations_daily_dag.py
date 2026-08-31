"""
SAP Morocco — Pipeline A (GSOD stations) daily nowcast DAG.

⚠️  DEACTIVATED ON PURPOSE.  This DAG is shipped **paused**
(`is_paused_upon_creation=True`) so it appears in the Airflow UI but never runs
on its own until the rest of the system is finished. Un-pause it (UI toggle or
`airflow dags unpause stations_daily`) once every component is wired.

Runs every day at 05:30 (Africa/Casablanca), one hour before the ERA5
`sap_pipeline`, and chains the two stages of the station pipeline:

    ingest_openmeteo  ->  forecast_gru

  1. ingest_openmeteo  BashOperator — openmeteo/openmeteo_producer.py: pulls the
                                      last 7 days for every registered station
                                      from Open-Meteo (rate-limited), writes the
                                      cleaned CSVs and mirrors them to MinIO under
                                      raw/stations/openmeteo/.
  2. forecast_gru      BashOperator — backend/predict_stations.py: loads the GRU
                                      model, turns each station's last 7 days into
                                      a 7-day Heat-Index / Wind-Chill forecast and
                                      writes public/data/stations_forecast.geojson
                                      (served by GET /alerts/stations).

Mirrors the conventions of `sap_pipeline_dag.py` (same mount layout, owner,
retry policy). Unlike the ERA5 pipeline there is no Spark/tensor hand-off, so the
two Bash steps run back-to-back with no sensor in between.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from airflow import DAG
from airflow.operators.bash import BashOperator

logger = logging.getLogger("sap.dag.stations")

# Container paths (see docker-compose volume mounts on the Airflow services).
OPENMETEO_DIR = "/opt/airflow/openmeteo"
BACKEND_DIR = "/opt/airflow/backend"
REPO_ROOT = "/opt/airflow"

DEFAULT_ARGS = {
    "owner": "sap-mlops",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "depends_on_past": False,
}

with DAG(
    dag_id="stations_daily",
    description="Daily GSOD-station nowcast for Morocco (Open-Meteo -> GRU).",
    schedule="30 5 * * *",
    start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=True,  # ⚠️ ships paused — un-pause when everything is ready
    default_args=DEFAULT_ARGS,
    tags=["sap", "morocco", "mlops", "stations", "gru"],
) as dag:

    # ---- Task 1: live ingestion from Open-Meteo (rate-limited) ----
    ingest_openmeteo = BashOperator(
        task_id="ingest_openmeteo",
        bash_command=(
            f"cd {REPO_ROOT} && "
            f"python {OPENMETEO_DIR}/openmeteo_producer.py --days 7"
        ),
    )

    # ---- Task 2: GRU inference -> stations_forecast.geojson ----
    forecast_gru = BashOperator(
        task_id="forecast_gru",
        bash_command=(
            f"cd {REPO_ROOT} && "
            f"python {BACKEND_DIR}/predict_stations.py "
            f"--stations data/live/openmeteo "
            f"--out public/data/stations_forecast.geojson"
        ),
    )

    ingest_openmeteo >> forecast_gru
