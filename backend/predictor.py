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
CLIMATOLOGY_FILE = ARTIFACTS_DIR / "seuils_climatologiques_mensuels.nc"

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
    if "month" in ds.dims:
        ds = ds.isel(month=month_index)
    tmax_90p = ds["tmax_90p"].values.astype(np.float32)
    tmin_10p = ds["tmin_10p"].values.astype(np.float32)
    ds.close()
    return tmax_90p, tmin_10p


# ---------------------------------------------------------------------------
# GeoJSON builder
# ---------------------------------------------------------------------------
def _severity_to_alert_level(severity: float) -> str:
    if severity > 5.0:
        return "red"
    if severity > 2.0:
        return "orange"
    return "yellow"


def _build_geojson(
    severity_matrix: np.ndarray,          # [lat, lon]
    predicted_tmax: np.ndarray,            # [lat, lon]   (Day‑1)
    latitudes: np.ndarray,                 # [lat,]
    longitudes: np.ndarray,                # [lon,]
) -> dict:
    """
    Convert anomalous pixels into a GeoJSON FeatureCollection.

    Only pixels with severity > 0 are emitted.
    """
    features = []
    lat_grid, lon_grid = np.meshgrid(latitudes, longitudes, indexing="ij")

    rows, cols = np.where(severity_matrix > 0)

    for r, c in zip(rows, cols):
        features.append({
            "type": "Feature",
            "geometry": {
                "type":        "Point",
                "coordinates": [float(lon_grid[r, c]), float(lat_grid[r, c])],
            },
            "properties": {
                "region_lat":    float(latitudes[r]),
                "region_lon":    float(longitudes[c]),
                "alert_level":   _severity_to_alert_level(float(severity_matrix[r, c])),
                "predicted_temp": float(round(predicted_tmax[r, c], 1)),
                "severity":      float(round(severity_matrix[r, c], 1)),
                "threshold":     "tmax_90p",
            },
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
        filters=32, kernel_size=3,
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
    #  Shape from disk:  [T_days, lat, lon, channels]  e.g. [7, 37, 65, 7]
    raw_tensor = np.load(tensor_path).astype(np.float32)
    logger.info("Loaded tensor shape: %s", raw_tensor.shape)

    # Reorder to:  [B=1, T=7, C=7, H=37, W=65]
    #   raw_tensor:  [T, H, W, C] → transpose to [T, C, H, W]
    tensor_tch = raw_tensor.transpose(0, 3, 1, 2)
    tensor_tch = torch.from_numpy(tensor_tch).unsqueeze(0).to(device)

    # ---- 3. Forward pass ----
    with torch.no_grad():
        pred_norm = model(tensor_tch)          # [1, 7, 3, 37, 65]

    # ---- 4. Denormalise predictions ----
    mean_all, std_all = _load_normalisation_stats()
    # Target channels are the first 3: tmax, tmin, rh
    mean_targ = torch.from_numpy(mean_all[:3]).view(1, 1, 3, 1, 1).to(device)
    std_targ  = torch.from_numpy(std_all[:3]).view(1, 1, 3, 1, 1).to(device)

    pred_phys = pred_norm * std_targ + mean_targ     # [1, 7, 3, 37, 65]

    # Extract Day‑1  (index 0 in output_window dimension)
    pred_d1 = pred_phys[0, 0]                         # [3, 37, 65]
    pred_tmax = pred_d1[0].cpu().numpy()              # [37, 65]
    pred_tmin = pred_d1[1].cpu().numpy()              # [37, 65]  (unused for heatwave but available)

    # ---- 5. Climatology comparison ----
    current_month = (datetime.utcnow() - timedelta(days=5)).month
    month_idx = current_month - 1                     # 0‑based index

    tmax_90p, tmin_10p = _load_climatology(month_idx)

    severity_tmax = pred_tmax - tmax_90p              # > 0 → hotter than 90th pct
    # Optional: cold-severity for frost alerts
    severity_tmin = tmin_10p - pred_tmin              # > 0 → colder than 10th pct

    logger.info(
        "Heatwave pixels  (severity > 0): %d / %d",
        int(np.sum(severity_tmax > 0)),
        severity_tmax.size,
    )
    logger.info(
        "Frost-risk pixels (severity > 0): %d / %d",
        int(np.sum(severity_tmin > 0)),
        severity_tmin.size,
    )

    # ---- 6. Build GeoJSON (heatwave focus) ----
    # Reconstruct lat/lon arrays for 37×65 grid over Morocco
    lats = np.linspace(36, 27, 37, endpoint=True)     # North → South
    lons = np.linspace(-17, -1, 65, endpoint=True)     # West  → East

    geojson = _build_geojson(severity_tmax, pred_tmax, lats, lons)

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
