"""
MinIO / S3 DataLake client for SAP Morocco.

A thin, dependency-light wrapper around ``boto3`` that talks to the MinIO
``sap-datalake`` bucket. Used by the inference job to read live tensors /
climatology and to archive raw predictions, and by the FastAPI point-query
endpoint to read the latest prediction back.

Configuration is taken entirely from the environment so the same code runs
locally, inside the ``predictor`` container, and inside Airflow workers:

    MINIO_ENDPOINT     default http://localhost:9000
    MINIO_ACCESS_KEY   default minioadmin   (falls back to MINIO_ROOT_USER)
    MINIO_SECRET_KEY   default minioadmin   (falls back to MINIO_ROOT_PASSWORD)
    MINIO_BUCKET       default sap-datalake
    MINIO_REGION       default us-east-1

Canonical bucket layout
-----------------------
    raw/            era5_live_surface_YYYYMMDD.nc, era5_live_pressure_YYYYMMDD.nc
    tensors/        tensor_live_YYYYMMDD.npy            (Spark output)
    reference/      normalization.npz, seuils_climatologiques_globaux.nc
    predictions/    raw_pred_YYYYMMDD.npy               (denormalised [7,3,37,65])
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

logger = logging.getLogger("sap.storage")

# ---------------------------------------------------------------------------
# Environment-driven defaults
# ---------------------------------------------------------------------------
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY") or os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY") or os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "sap-datalake")
MINIO_REGION = os.getenv("MINIO_REGION", "us-east-1")

# Canonical object-key prefixes
RAW_PREFIX = "raw/"
TENSOR_PREFIX = "tensors/"
REFERENCE_PREFIX = "reference/"
PREDICTIONS_PREFIX = "predictions/"

CLIMATOLOGY_KEY = REFERENCE_PREFIX + "seuils_climatologiques_globaux.nc"
NORMALIZATION_KEY = REFERENCE_PREFIX + "normalization.npz"


class S3Storage:
    """Minimal S3/MinIO helper exposing the few operations the pipeline needs."""

    def __init__(
        self,
        bucket: str = MINIO_BUCKET,
        endpoint_url: str = MINIO_ENDPOINT,
        access_key: str = MINIO_ACCESS_KEY,
        secret_key: str = MINIO_SECRET_KEY,
        region: str = MINIO_REGION,
    ) -> None:
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
        )

    # -- bucket -------------------------------------------------------------
    def ensure_bucket(self) -> None:
        """Create the bucket if it does not already exist (idempotent)."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            logger.info("Creating bucket '%s'", self.bucket)
            self.client.create_bucket(Bucket=self.bucket)

    # -- existence / listing ------------------------------------------------
    def object_exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def list_objects(self, prefix: str = "") -> list[dict]:
        """Return the raw ``Contents`` dicts for every object under *prefix*."""
        objects: list[dict] = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            objects.extend(page.get("Contents", []))
        return objects

    def latest_object(self, prefix: str, suffix: Optional[str] = None) -> Optional[dict]:
        """
        Return the most recently modified object under *prefix* (optionally
        filtered by *suffix*), or ``None`` when nothing matches.
        """
        candidates = [
            obj
            for obj in self.list_objects(prefix)
            if suffix is None or obj["Key"].endswith(suffix)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda o: o["LastModified"])

    def latest_key(self, prefix: str, suffix: Optional[str] = None) -> Optional[str]:
        obj = self.latest_object(prefix, suffix)
        return obj["Key"] if obj else None

    # -- transfer -----------------------------------------------------------
    def upload_file(self, local_path: str | Path, key: str) -> str:
        self.client.upload_file(str(local_path), self.bucket, key)
        logger.info("Uploaded %s -> s3://%s/%s", local_path, self.bucket, key)
        return key

    def upload_bytes(self, data: bytes, key: str) -> str:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)
        logger.info("Uploaded %d bytes -> s3://%s/%s", len(data), self.bucket, key)
        return key

    def download_file(self, key: str, local_path: str | Path) -> Path:
        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, str(local_path))
        logger.info("Downloaded s3://%s/%s -> %s", self.bucket, key, local_path)
        return local_path

    def download_bytes(self, key: str) -> bytes:
        resp = self.client.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"].read()


def get_storage() -> Optional[S3Storage]:
    """
    Build an :class:`S3Storage` instance, returning ``None`` (and logging) when
    MinIO is unreachable so callers can transparently fall back to local files.
    """
    try:
        storage = S3Storage()
        storage.ensure_bucket()
        return storage
    except Exception:  # noqa: BLE001 — any connectivity/credential error
        logger.warning("MinIO/S3 unavailable — falling back to local filesystem", exc_info=True)
        return None
