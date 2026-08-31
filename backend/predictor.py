"""
PyTorch Inference & Anomaly Detection for SAP Morocco — MinIO DataLake edition.

Workflow:
  1. Pull the latest `tensor_live_*.npy` and the climatology percentiles
     (`seuils_climatologiques_globaux.nc`) from the MinIO DataLake
     (falls back to local folders when MinIO is unavailable).
  2. Load the trained model weights (cnn3d_best.pth / convlstm fallback).
  3. Run forward pass -> 7-day forecast (tmax, tmin, rh) and denormalise.
  4. Archive the raw denormalised tensor [7, 3, 37, 65] back to MinIO under
     `predictions/raw_pred_YYYYMMDD.npy` (this is what the on-demand point API
     reads later).
  5. For each Moroccan city: extract the nearest grid cell, apply the NOAA
     Heat Index, compare tmax against the monthly 90th-percentile climatology
     and emit a lightweight `today_alerts.geojson` (local + optional PostGIS).

Usage:
    python backend/predictor.py                 # MinIO -> latest tensor
    python backend/predictor.py --file t.npy    # explicit local tensor
    python backend/predictor.py --no-minio      # force local-only mode
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import torch
import xarray as xr

from app.core.meteo import (
    CH_HEAT_INDEX,
    CH_WIND_CHILL,
    FORECAST_HORIZON,
    GRID_COLS,
    GRID_LATS,
    GRID_LONS,
    GRID_ROWS,
    MOROCCO_CITIES,
    STAT_HEAT_INDEX_IDX,
    STAT_WIND_CHILL_IDX,
    felt_severity,
    nearest_grid_index,
    severity_to_alert_level,
)
from app.core.storage import (
    CLIMATOLOGY_KEY,
    PREDICTIONS_PREFIX,
    TENSOR_PREFIX,
    get_storage,
)

# ---------------------------------------------------------------------------
# Project-root resolution  (works from backend/ or repo root)
# ---------------------------------------------------------------------------
CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parent
PROJECT_ROOT = BACKEND_DIR.parent

ARTIFACTS_DIR = BACKEND_DIR / "artifacts"
READY_DIR = PROJECT_ROOT / "data" / "ready_for_inference"
OUTPUT_GEOJSON = PROJECT_ROOT / "public" / "data" / "today_alerts.geojson"

MODEL_WEIGHTS = ARTIFACTS_DIR / "convlstm_best.pt"
NORM_STATS = ARTIFACTS_DIR / "normalization.npz"
CLIMATOLOGY_FILE = ARTIFACTS_DIR / "seuils_climatologiques_globaux.nc"

OUTPUT_GEOJSON.parent.mkdir(parents=True, exist_ok=True)

# Optional serving database (PostGIS). When unset, only the GeoJSON is written.
SERVING_DB_URL = os.getenv("SERVING_DB_URL")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("SAP-Predictor")


# ---------------------------------------------------------------------------
# DataLake resolution helpers
# ---------------------------------------------------------------------------
def _find_local_tensor() -> Path:
    files = sorted(READY_DIR.glob("tensor_live_*.npy"))
    if not files:
        raise FileNotFoundError(f"No .npy tensors found locally in {READY_DIR}")
    return files[-1]


def _resolve_tensor(storage, explicit: Optional[Path], tmp_dir: Path) -> Tuple[Path, str]:
    """
    Return (local_path, date_slug) for the input tensor.

    Priority: explicit --file > latest tensor in MinIO > latest local tensor.
    """
    if explicit is not None:
        return explicit, _date_slug_from_name(explicit.name)

    if storage is not None:
        key = storage.latest_key(TENSOR_PREFIX, suffix=".npy")
        if key:
            local = tmp_dir / Path(key).name
            storage.download_file(key, local)
            return local, _date_slug_from_name(Path(key).name)
        logger.warning("No tensor found in MinIO under '%s' — trying local", TENSOR_PREFIX)

    local = _find_local_tensor()
    return local, _date_slug_from_name(local.name)


def _resolve_climatology(storage, tmp_dir: Path) -> Path:
    """Return a local path to the climatology NetCDF (MinIO first, then local)."""
    if storage is not None and storage.object_exists(CLIMATOLOGY_KEY):
        local = tmp_dir / "seuils_climatologiques_globaux.nc"
        storage.download_file(CLIMATOLOGY_KEY, local)
        return local
    return CLIMATOLOGY_FILE


def _date_slug_from_name(name: str) -> str:
    """Extract an 8-digit YYYYMMDD slug from a filename, else use today (UTC)."""
    for token in name.replace(".", "_").split("_"):
        if len(token) == 8 and token.isdigit():
            return token
    return datetime.utcnow().strftime("%Y%m%d")


N_INPUT_CHANNELS = 13  # must match ingestion_2/era5land_processor.py


def _target_indices() -> list[int]:
    """
    Indices of the predicted targets (HeatIndex, WindChill) inside the 13-channel
    stats, resolved from normalization.npz's channels/target_channels. Falls back
    to [11, 12] (the canonical positions) when those arrays are absent.
    """
    try:
        s = np.load(NORM_STATS, allow_pickle=True)
        if "channels" in s and "target_channels" in s:
            chans = [str(x) for x in s["channels"]]
            tgts = [str(x) for x in s["target_channels"]]
            idx = [chans.index(t) for t in tgts]
            if len(idx) == 2:
                return idx
    except (OSError, ValueError, KeyError):
        pass
    return [STAT_HEAT_INDEX_IDX, STAT_WIND_CHILL_IDX]


def _load_normalisation_stats() -> Tuple[np.ndarray, np.ndarray]:
    stats = np.load(NORM_STATS, allow_pickle=True)
    mean = stats["mean"].astype(np.float32)
    std = stats["std"].astype(np.float32)
    # Mirror the processor: pad/truncate to the 13-channel input order so the
    # target indices (HeatIndex=11, WindChill=12) are always addressable. A
    # shorter stats file (e.g. 11 raw channels) means the two derived targets
    # were left in physical units -> identity (mean 0, std 1) denormalisation.
    n = len(mean)
    if n < N_INPUT_CHANNELS:
        mean = np.pad(mean, (0, N_INPUT_CHANNELS - n), constant_values=0.0)
        std = np.pad(std, (0, N_INPUT_CHANNELS - n), constant_values=1.0)
    elif n > N_INPUT_CHANNELS:
        mean = mean[:N_INPUT_CHANNELS]
        std = std[:N_INPUT_CHANNELS]
    std = np.where(std < 1e-6, 1.0, std)
    return mean, std


def _load_climatology(path: Path) -> Tuple[np.ndarray, np.ndarray]:
    if not path.exists():
        logger.warning(
            "%s not found — using fallback thresholds (tmax=45 C, tmin=0 C). "
            "Run the climatology builder to populate real percentiles.",
            path,
        )
        tmax_90p = np.full((GRID_ROWS, GRID_COLS), 45.0, dtype=np.float32)
        tmin_10p = np.full((GRID_ROWS, GRID_COLS), 0.0, dtype=np.float32)
        return tmax_90p, tmin_10p

    ds = xr.open_dataset(path, engine="netcdf4")
    ds = ds.sel(latitude=slice(36, 27), longitude=slice(-17, -1))
    tmax_90p = ds["tmax_90p"].values.astype(np.float32)
    tmin_10p = ds["tmin_10p"].values.astype(np.float32)
    ds.close()
    return tmax_90p, tmin_10p


# ---------------------------------------------------------------------------
# City-based GeoJSON builder
# ---------------------------------------------------------------------------
def _build_city_geojson(
    pred_hi: np.ndarray,    # [7, lat, lon] predicted Heat Index
    pred_wc: np.ndarray,    # [7, lat, lon] predicted Wind Chill
) -> dict:
    """One GeoJSON Feature per Moroccan city, each with its 7-day forecast."""
    start_date = datetime.utcnow()
    features = []

    for city in MOROCCO_CITIES:
        r, c = nearest_grid_index(city["lat"], city["lon"])

        day_forecasts = []
        max_severity = -999.0

        for d in range(FORECAST_HORIZON):
            hi_val = float(pred_hi[d, r, c])
            wc_val = float(pred_wc[d, r, c])

            # Severity is derived solely from the predicted felt-temperatures.
            severity = felt_severity(hi_val, wc_val)
            max_severity = max(max_severity, severity)

            forecast_date = (start_date + timedelta(days=d)).strftime("%Y-%m-%d")
            day_forecasts.append(
                {
                    "day": d,
                    "date": forecast_date,
                    "heat_index": round(hi_val, 1),
                    "wind_chill": round(wc_val, 1),
                    "severity": round(max(0.0, severity), 1),
                    "alert_level": severity_to_alert_level(severity),
                }
            )

        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [city["lon"], city["lat"]]},
                "properties": {
                    "name": city["name"],
                    "alert_level": severity_to_alert_level(max_severity),
                    "severity": round(max(0.0, max_severity), 1),
                    "forecasts": day_forecasts,
                },
            }
        )

    logger.info("GeoJSON: %d city features built", len(features))
    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# Optional PostGIS serving write
# ---------------------------------------------------------------------------
def _write_to_postgis(geojson: dict) -> None:
    """
    Best-effort upsert of the city alerts into PostGIS so FastAPI can serve them
    from the database. No-op (with a warning) when SERVING_DB_URL is unset or the
    DB is unreachable — the GeoJSON file remains the source of truth either way.
    """
    if not SERVING_DB_URL:
        return

    try:
        import psycopg2
        from psycopg2.extras import Json
    except ImportError:
        logger.warning("psycopg2 not installed — skipping PostGIS write")
        return

    try:
        conn = psycopg2.connect(SERVING_DB_URL)
    except Exception:  # noqa: BLE001
        logger.warning("Cannot connect to serving DB — skipping PostGIS write", exc_info=True)
        return

    try:
        with conn, conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS city_alerts (
                    name        TEXT PRIMARY KEY,
                    alert_level TEXT NOT NULL,
                    severity    DOUBLE PRECISION NOT NULL,
                    forecasts   JSONB NOT NULL,
                    geom        geometry(Point, 4326) NOT NULL,
                    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            for feat in geojson["features"]:
                lon, lat = feat["geometry"]["coordinates"]
                props = feat["properties"]
                cur.execute(
                    """
                    INSERT INTO city_alerts (name, alert_level, severity, forecasts, geom, updated_at)
                    VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), now())
                    ON CONFLICT (name) DO UPDATE SET
                        alert_level = EXCLUDED.alert_level,
                        severity    = EXCLUDED.severity,
                        forecasts   = EXCLUDED.forecasts,
                        geom        = EXCLUDED.geom,
                        updated_at  = now();
                    """,
                    (props["name"], props["alert_level"], props["severity"],
                     Json(props["forecasts"]), lon, lat),
                )
        logger.info("PostGIS: upserted %d city alerts", len(geojson["features"]))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------
def _extract_state_dict(obj: object) -> dict:
    if isinstance(obj, dict) and "model" in obj:
        return obj["model"]
    if isinstance(obj, dict):
        return obj
    raise TypeError("Unsupported checkpoint format")


def _infer_model_type(state: dict) -> str:
    keys = set(state.keys())
    if any(k.startswith("conv3d.") for k in keys):
        return "cnn3d"
    if any(k.startswith("enc_cell1.") for k in keys) or any(k.startswith("dec_cell.") for k in keys):
        return "convlstm"
    return "convlstm"


def _load_model(device: str):
    from models import CNN3D, Seq2SeqConvLSTM

    if MODEL_WEIGHTS.exists():
        raw_state = torch.load(MODEL_WEIGHTS, map_location=device)
        state = _extract_state_dict(raw_state)
        model_type = _infer_model_type(state)

        if model_type == "cnn3d":
            model = CNN3D(n_in=13, n_out=2, output_window=FORECAST_HORIZON)
        else:
            model = Seq2SeqConvLSTM(
                input_window=7, output_window=FORECAST_HORIZON,
                lat=GRID_ROWS, lon=GRID_COLS, n_in=11, n_out=2,
                filters=64, kernel_size=3,
            )
        model.load_state_dict(state)
        logger.info("Loaded %s weights from %s", model_type, MODEL_WEIGHTS)
    else:
        logger.error(
            "Model weights NOT FOUND at %s — running with random init. "
            "Predictions are meaningless.",
            MODEL_WEIGHTS,
        )
        model = Seq2SeqConvLSTM(
            input_window=7, output_window=FORECAST_HORIZON,
            lat=GRID_ROWS, lon=GRID_COLS, n_in=11, n_out=2,
            filters=64, kernel_size=3,
        )

    model.to(device)
    model.eval()
    return model


def _prepare_input(tensor_path: Path, device: str) -> torch.Tensor:
    raw_tensor = np.load(tensor_path).astype(np.float32)
    logger.info("Loaded tensor shape: %s", raw_tensor.shape)

    tensor_tch = raw_tensor.transpose(0, 3, 1, 2)                 # [T, C, H, W]
    tensor_tch = torch.from_numpy(tensor_tch).unsqueeze(0).to(device)  # [1, T, C, H, W]

    if tensor_tch.shape[1] > 7:
        tensor_tch = tensor_tch[:, -7:, ...]
    if tensor_tch.shape[1] != 7:
        raise ValueError(f"Input tensor must contain exactly 7 days, got {tensor_tch.shape[1]}")

    logger.info(
        "Debug input tensor: min=%.2f, max=%.2f, has_nan=%s",
        tensor_tch.min().item(), tensor_tch.max().item(),
        torch.isnan(tensor_tch).any().item(),
    )

    if tensor_tch.shape[-2:] != (GRID_ROWS, GRID_COLS):
        import torch.nn.functional as F
        B, T, C, H, W = tensor_tch.shape
        tensor_tch = tensor_tch.view(B * T, C, H, W)
        tensor_tch = F.interpolate(
            tensor_tch, size=(GRID_ROWS, GRID_COLS), mode="bilinear", align_corners=False
        )
        tensor_tch = tensor_tch.view(B, T, C, GRID_ROWS, GRID_COLS)

    return torch.nan_to_num(tensor_tch, nan=0.0)


# ---------------------------------------------------------------------------
# Inference pipeline
# ---------------------------------------------------------------------------
def run_inference(
    tensor_path: Optional[Path] = None,
    device: str = "cpu",
    use_minio: bool = True,
) -> Path:
    logger.info("=" * 60)
    logger.info("START Inference | device=%s | minio=%s", device, use_minio)

    storage = get_storage() if use_minio else None

    with tempfile.TemporaryDirectory(prefix="sap_predict_") as tmp:
        tmp_dir = Path(tmp)

        # ---- 1. Resolve inputs from the DataLake ----
        local_tensor, date_slug = _resolve_tensor(storage, tensor_path, tmp_dir)
        logger.info("Tensor: %s | date_slug=%s", local_tensor.name, date_slug)

        # ---- 2. Model + input ----
        model = _load_model(device)
        tensor_tch = _prepare_input(local_tensor, device)

        # ---- 3. Forward pass ----
        # The 13-channel tensor carries 11 model inputs (ch 0-10) plus the two
        # prediction targets (HeatIndex ch 11, WindChill ch 12). Feed inputs only.
        with torch.no_grad():
            pred_norm = model(tensor_tch[:, :, :N_INPUT_CHANNELS - 2, :, :])  # [1, 7, 2, 37, 65]

        # ---- 4. Denormalise ----
        # The model outputs the 2 target channels (HeatIndex, WindChill) in z-score
        # space. Denormalise with those targets' own stats, located via the
        # target_channels saved in normalization.npz (HeatIndex@11, WindChill@12).
        # The targets are already in °C, so no Kelvin conversion.
        mean_all, std_all = _load_normalisation_stats()
        targ_idx = _target_indices()
        mean_targ = torch.from_numpy(mean_all[targ_idx]).view(1, 1, 2, 1, 1).to(device)
        std_targ = torch.from_numpy(std_all[targ_idx]).view(1, 1, 2, 1, 1).to(device)

        pred_phys = pred_norm * std_targ + mean_targ
        pred_7d = pred_phys[0].cpu().numpy().astype(np.float32)  # [7, 2, 37, 65]
        logger.info("Denormalised prediction shape: %s", pred_7d.shape)

        # ---- 5. Archive raw denormalised tensor to the DataLake ----
        if storage is not None:
            buf = io.BytesIO()
            np.save(buf, pred_7d)
            pred_key = f"{PREDICTIONS_PREFIX}raw_pred_{date_slug}.npy"
            storage.upload_bytes(buf.getvalue(), pred_key)
        else:
            local_pred = READY_DIR / f"raw_pred_{date_slug}.npy"
            np.save(local_pred, pred_7d)
            logger.info("Saved raw prediction locally -> %s", local_pred)

        # ---- 6. City GeoJSON (severity from felt-temperatures only) ----
        pred_hi = pred_7d[:, CH_HEAT_INDEX, :, :]
        pred_wc = pred_7d[:, CH_WIND_CHILL, :, :]
        logger.info(
            "Debug pred heat_index/wind_chill mean: %.2f / %.2f",
            pred_hi.mean(), pred_wc.mean(),
        )

        geojson = _build_city_geojson(pred_hi, pred_wc)

    # ---- 7. Persist serving artifacts ----
    with open(OUTPUT_GEOJSON, "w", encoding="utf-8") as fh:
        json.dump(geojson, fh, indent=2)
    logger.info("GeoJSON written -> %s", OUTPUT_GEOJSON)

    _write_to_postgis(geojson)

    logger.info("Inference completed. %d cities output.", len(geojson["features"]))
    return OUTPUT_GEOJSON


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SAP Morocco — Inference & Alerting (MinIO)")
    p.add_argument(
        "--file", type=Path, default=None,
        help="Path to a specific local .npy tensor (default: latest from MinIO)",
    )
    p.add_argument(
        "--device", type=str, default=os.getenv("INFERENCE_DEVICE", "cpu"),
        help="Device: cpu | cuda | mps",
    )
    p.add_argument(
        "--no-minio", action="store_true",
        help="Force local-only mode (skip the MinIO DataLake)",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    try:
        run_inference(tensor_path=args.file, device=args.device, use_minio=not args.no_minio)
    except Exception:
        logger.exception("Fatal error during inference pipeline")
        sys.exit(1)
