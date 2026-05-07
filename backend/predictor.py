"""
PyTorch Inference & Anomaly Detection for SAP Morocco.

Workflow:
  1. Load trained Seq2SeqConvLSTM weights (convlstm_pytorch_best.pth)
  2. Load the latest .npy tensor from ready_for_inference/
  3. Run forward pass → 7-day forecast (tmax, tmin, rh)
  4. Denormalise predictions to physical degrees Celsius
  5. Compare Day‑1 tmax/tmin against monthly climatological percentiles
  6. Generate GeoJSON FeatureCollection for the frontend Leaflet map

Usage:
    python backend/predictor.py          # processes latest tensor
    python backend/predictor.py --file path/to/tensor.npy  # explicit tensor
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import torch
import xarray as xr

# ---------------------------------------------------------------------------
# Project‑root resolution  (works from backend/ or repo root)
# ---------------------------------------------------------------------------
CURRENT_FILE  = Path(__file__).resolve()
BACKEND_DIR   = CURRENT_FILE.parent if CURRENT_FILE.name == "predictor.py" else CURRENT_FILE
PROJECT_ROOT  = BACKEND_DIR.parent

ARTIFACTS_DIR = BACKEND_DIR / "artifacts"
READY_DIR     = PROJECT_ROOT / "data" / "ready_for_inference"
OUTPUT_GEOJSON = PROJECT_ROOT / "public" / "data" / "today_alerts.geojson"

MODEL_WEIGHTS    = ARTIFACTS_DIR / "convlstm_pytorch_best.pth"
NORM_STATS       = ARTIFACTS_DIR / "normalization.npz"
CLIMATOLOGY_FILE = ARTIFACTS_DIR / "seuils_climatologiques_globaux.nc"

OUTPUT_GEOJSON.parent.mkdir(parents=True, exist_ok=True)

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
# Helpers
# ---------------------------------------------------------------------------
def _find_latest_tensor() -> Path:
    """Return the most-recent .npy file under READY_DIR."""
    files = sorted(READY_DIR.glob("tensor_live_*.npy"))
    if not files:
        raise FileNotFoundError(f"No .npy tensors found in {READY_DIR}")
    return files[-1]


def _load_normalisation_stats() -> Tuple[np.ndarray, np.ndarray]:
    """
    Returns (mean, std) of shape (7,).

    Channel mapping (index → variable):
      0: tmax,  1: tmin,  2: rh,  3: u10,  4: v10,  5: z500,  6: t850

    Only the first 3 channels (tmax, tmin, rh) are needed for denormalisation
    of predictions, but the file contains all 7.
    """
    stats = np.load(NORM_STATS, allow_pickle=True)
    mean = stats["mean"].astype(np.float32)
    std  = stats["std"].astype(np.float32)
    std  = np.where(std < 1e-6, 1.0, std)
    return mean, std


def _load_climatology(month_index: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    Load monthly climatological percentiles for heatwave / cold detection.

    Returns (tmax_90p, tmin_10p), each of shape [lat, lon] in degrees C.

    Falls back to conservative defaults when the file is missing.
    """
    if not CLIMATOLOGY_FILE.exists():
        logger.warning(
            "%s not found — using fallback thresholds "
            "(tmax=45 °C, tmin=0 °C).  "
            "Run the climatology builder to populate real percentiles.",
            CLIMATOLOGY_FILE,
        )
        # 37×65 dummy grids
        tmax_90p = np.full((37, 65), 45.0, dtype=np.float32)
        tmin_10p = np.full((37, 65),  0.0, dtype=np.float32)
        return tmax_90p, tmin_10p

    ds = xr.open_dataset(CLIMATOLOGY_FILE, engine="netcdf4")
    
    # We must match the spatial domain of the model (37x65)
    # The model domain is [36, -17, 27, -1] (N, W, S, E)
    ds = ds.sel(latitude=slice(36, 27), longitude=slice(-17, -1))
    
    # Read the global precalculated percentiles
    tmax_90p = ds["tmax_90p"].values.astype(np.float32)
    tmin_10p = ds["tmin_10p"].values.astype(np.float32)

    ds.close()
    return tmax_90p, tmin_10p


# ---------------------------------------------------------------------------
# GeoJSON builder
# ---------------------------------------------------------------------------
def _severity_to_alert_level(severity: float) -> str:
    if severity <= 0.0:
        return "none"
    if severity > 5.0:
        return "red"
    if severity > 2.0:
        return "orange"
    return "yellow"


def _build_geojson(
    tmax_90p: np.ndarray,                  # [lat, lon]
    pred_tmax: np.ndarray,                 # [7, lat, lon]
    pred_tmin: np.ndarray,                 # [7, lat, lon]
    pred_rh: np.ndarray,                   # [7, lat, lon]
    pred_hi: np.ndarray,                   # [7, lat, lon]
    latitudes: np.ndarray,                 # [lat,]
    longitudes: np.ndarray,                # [lon,]
) -> dict:
    """
    Convert anomalous pixels into a GeoJSON FeatureCollection.

    Pixels that have a severity > 0 on ANY of the 7 days are emitted
    with their full 7-day array payloads.
    Ocean pixels (NaN in climatology) are skipped.
    """
    features = []
    lat_grid, lon_grid = np.meshgrid(latitudes, longitudes, indexing="ij")

    # Loop over spatial grid
    for r in range(latitudes.shape[0]):
        for c in range(longitudes.shape[0]):
            # ========================================================
            # Ocean Mask : ERA5-Land met des NaN sur l'océan
            # ========================================================
            if np.isnan(tmax_90p[r, c]):
                continue

            # Sécurité supplémentaire : ignorer les seuils suspects
            if tmax_90p[r, c] < 5:
                continue

            pixel_forecasts = []
            has_alert = False

            # Loop over the 7 forecast days
            for d in range(7):
                tmax_val = float(pred_tmax[d, r, c])
                tmin_val = float(pred_tmin[d, r, c])
                rh_val   = float(pred_rh[d, r, c])
                hi_val   = float(pred_hi[d, r, c])

                severity = tmax_val - tmax_90p[r, c]
                alert = _severity_to_alert_level(severity)

                if alert != "none":
                    has_alert = True

                forecast_date = (datetime.utcnow() + timedelta(days=d)).strftime("%Y-%m-%d")

                pixel_forecasts.append({
                    "day": d,
                    "date": forecast_date,
                    "tmax": float(round(tmax_val, 1)),
                    "tmin": float(round(tmin_val, 1)),
                    "rh": float(round(rh_val, 1)),
                    "heat_index": float(round(hi_val, 1)),
                    "severity": float(round(max(0.0, float(severity)), 1)),
                    "alert_level": alert
                })

            # Add to map ONLY if it triggers an alert at least once during the week
            if has_alert:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [float(lon_grid[r, c]), float(lat_grid[r, c])]},
                    "properties": {
                        "region_lat": float(latitudes[r]),
                        "region_lon": float(longitudes[c]),
                        "forecasts": pixel_forecasts
                    }
                })

    logger.info("GeoJSON: %d anomalous point features", len(features))

    return {
        "type": "FeatureCollection",
        "features": features,
    }


# ---------------------------------------------------------------------------
# Inference pipeline
# ---------------------------------------------------------------------------
def run_inference(tensor_path: Optional[Path] = None, device: str = "cpu") -> Path:
    """
    Main inference routine.

    Returns the path to the written GeoJSON file.
    """
    if tensor_path is None:
        tensor_path = _find_latest_tensor()

    logger.info("=" * 60)
    logger.info("START Inference | tensor: %s", tensor_path.name)

    # ---- 1. Load model ----
    from models import Seq2SeqConvLSTM

    model = Seq2SeqConvLSTM(
        input_window=7, output_window=7,
        lat=37, lon=65, n_in=7, n_out=3,
        filters=64, kernel_size=3,
    )

    if MODEL_WEIGHTS.exists():
        state = torch.load(MODEL_WEIGHTS, map_location=device)
        model.load_state_dict(state)
        logger.info("Loaded weights from %s", MODEL_WEIGHTS)
    else:
        logger.error(
            "Model weights NOT FOUND at %s — "
            "running with random initialization. Predictions are meaningless.",
            MODEL_WEIGHTS,
        )

    model.to(device)
    model.eval()

    # ---- 2. Load & prepare input tensor ----
    #  Shape from disk:  [T_days, lat, lon, channels]  e.g. [31, 91, 161, 7]
    raw_tensor = np.load(tensor_path).astype(np.float32)
    logger.info("Loaded tensor shape: %s", raw_tensor.shape)

    # Reorder to:  [B=1, T, C, H, W]
    #   raw_tensor:  [T, H, W, C] → transpose to [T, C, H, W]
    tensor_tch = raw_tensor.transpose(0, 3, 1, 2)
    tensor_tch = torch.from_numpy(tensor_tch).unsqueeze(0).to(device)

    # The model was trained on 7 days of context and 37x65 resolution (0.25 deg grid).
    if tensor_tch.shape[1] > 7:
        tensor_tch = tensor_tch[:, -7:, ...]
        
    logger.info("Debug Input tensor: min=%.2f, max=%.2f, has_nan=%s", tensor_tch.min().item(), tensor_tch.max().item(), torch.isnan(tensor_tch).any().item())
    
    if tensor_tch.shape[-2:] != (37, 65):
        B, T, C, H, W = tensor_tch.shape
        tensor_tch = tensor_tch.view(B * T, C, H, W)
        import torch.nn.functional as F
        tensor_tch = F.interpolate(tensor_tch, size=(37, 65), mode='bilinear', align_corners=False)
        tensor_tch = tensor_tch.view(B, T, C, 37, 65)

    # Replace NaNs that were present in the source files (e.g. ocean masking)
    # Since inputs are z-score normalized, filling with 0.0 corresponds to the historical mean.
    tensor_tch = torch.nan_to_num(tensor_tch, nan=0.0)

    # ---- 3. Forward pass ----
    with torch.no_grad():
        pred_norm = model(tensor_tch)          # [1, 7, 3, 37, 65]

    # ---- 4. Denormalise predictions ----
    mean_all, std_all = _load_normalisation_stats()
    # Target channels are the first 3: tmax, tmin, rh
    mean_targ = torch.from_numpy(mean_all[:3]).view(1, 1, 3, 1, 1).to(device)
    std_targ  = torch.from_numpy(std_all[:3]).view(1, 1, 3, 1, 1).to(device)

    pred_phys = pred_norm * std_targ + mean_targ     # [1, 7, 3, 37, 65]

    # Extract all 7 days for the 3 variables
    # pred_phys is [1, 7, 3, lats, lons]
    pred_7d = pred_phys[0].cpu().numpy()              # [7, 3, 37, 65]
    pred_tmax = pred_7d[:, 0, :, :]                   # [7, 37, 65]
    pred_tmin = pred_7d[:, 1, :, :]                   # [7, 37, 65]
    pred_rh   = pred_7d[:, 2, :, :]                   # [7, 37, 65]

    # Quick NWS approximation for Heat Index (simplified)
    # Vapor pressure (hPa) approx: e = (RH / 100) * 6.11 * 10.0 ** (7.5 * T / (237.3 + T))
    # HI approx = T + (0.5555 * (e - 10.0))
    e = (pred_rh / 100.0) * 6.105 * np.exp(17.27 * pred_tmax / (237.7 + pred_tmax))
    pred_hi = pred_tmax + 0.5555 * (e - 10.0)
    pred_hi = np.maximum(pred_tmax, pred_hi)  # HI only applies if it's hot and humid

    # ---- 5. Climatology comparison (Check across all 7 days) ----
    current_month = (datetime.utcnow() - timedelta(days=5)).month
    month_idx = current_month - 1                     # 0‑based index

    tmax_90p, tmin_10p = _load_climatology(month_idx)
    # Broadcast tmax_90p from [37, 65] to [7, 37, 65]
    tmax_90p_7d = np.expand_dims(tmax_90p, axis=0)
    tmin_10p_7d = np.expand_dims(tmin_10p, axis=0)

    severity_tmax = pred_tmax - tmax_90p_7d              # > 0 → hotter than 90th pct
    # severity_tmin = tmin_10p_7d - pred_tmin            # optional frost alert
    
    logger.info("Debug pred_tmax (mean across days): %.2f", pred_tmax.mean())
    logger.info("Debug tmax_90p mean: %.2f", tmax_90p.mean())

    # Replace with max severity over the 7 days to count
    logger.info(
        "Heatwave pixels  (severity > 0 any day): %d / %d",
        int(np.sum(np.max(severity_tmax, axis=0) > 0)),
        tmax_90p.size,
    )

    # ---- 6. Build GeoJSON (heatwave focus) ----
    lats = np.linspace(36, 27, 37, endpoint=True)     # North → South
    lons = np.linspace(-17, -1, 65, endpoint=True)     # West  → East

    geojson = _build_geojson(
        tmax_90p=tmax_90p,
        pred_tmax=pred_tmax,
        pred_tmin=pred_tmin,
        pred_rh=pred_rh,
        pred_hi=pred_hi,
        latitudes=lats,
        longitudes=lons,
    )

    with open(OUTPUT_GEOJSON, "w") as fh:
        json.dump(geojson, fh, indent=2)

    logger.info("GeoJSON written → %s", OUTPUT_GEOJSON)
    logger.info("Inference completed successfully.")
    return OUTPUT_GEOJSON


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SAP Morocco — Inference & Alerting")
    p.add_argument(
        "--file", type=Path, default=None,
        help="Path to a specific .npy tensor (default: newest in ready_for_inference/)",
    )
    p.add_argument(
        "--device", type=str, default=os.getenv("INFERENCE_DEVICE", "cpu"),
        help="Device: cpu | cuda | mps",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    try:
        run_inference(tensor_path=args.file, device=args.device)
    except Exception:
        logger.exception("Fatal error during inference pipeline")
        sys.exit(1)
