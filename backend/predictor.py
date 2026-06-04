"""
PyTorch Inference & Anomaly Detection for SAP Morocco – City-Based Extraction.

Workflow:
  1. Load trained Seq2SeqConvLSTM weights (convlstm_pytorch_best.pth)
  2. Load the latest .npy tensor from ready_for_inference/
  3. Run forward pass → 7-day forecast (tmax, tmin, rh)
  4. Denormalise predictions to physical degrees Celsius
  5. For each Moroccan city, extract the nearest-grid-cell 7-day forecast
  6. Apply NOAA Rothfusz Heat Index formula
  7. Compare tmax against monthly 90th-percentile climatology → severity
  8. Generate lightweight GeoJSON FeatureCollection (cities only, no ocean)

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

MODEL_WEIGHTS    = ARTIFACTS_DIR / "cnn3d_best.pth"
NORM_STATS       = ARTIFACTS_DIR / "normalization.npz"
CLIMATOLOGY_FILE = ARTIFACTS_DIR / "seuils_climatologiques_globaux.nc"

OUTPUT_GEOJSON.parent.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Moroccan Cities – top 20 major cities / regions
# (lat, lon) in decimal degrees; all within or near the model domain [36–27 N, 17–1 W]
# ---------------------------------------------------------------------------
MOROCCO_CITIES = [
    {"name": "Casablanca",      "lat": 33.5731,  "lon": -7.5898},
    {"name": "Rabat",            "lat": 34.0209,  "lon": -6.8416},
    {"name": "Marrakech",       "lat": 31.6295,  "lon": -7.9811},
    {"name": "Agadir",           "lat": 30.4278,  "lon": -9.5981},
    {"name":"Taroudant",        "lat": 30.4728,  "lon": -8.8732},
    {"name": "Fès",              "lat": 34.0331,  "lon": -5.0003},
    {"name": "Tanger",           "lat": 35.7595,  "lon": -5.8340},
    {"name": "Meknès",           "lat": 33.8920,  "lon": -5.5510},
    {"name": "Oujda",            "lat": 34.6814,  "lon": -1.9086},
    {"name": "Kénitra",          "lat": 34.2610,  "lon": -6.5802},
    {"name": "Tétouan",          "lat": 35.5889,  "lon": -5.3626},
    {"name": "Safi",             "lat": 32.2994,  "lon": -9.2372},
    {"name": "Mohammédia",       "lat": 33.3093,  "lon": -8.4552},
    {"name": "Béni Mellal",      "lat": 32.3373,  "lon": -6.3498},
    {"name": "Nador",            "lat": 35.1667,  "lon": -2.9333},
    {"name": "Taza",             "lat": 34.2155,  "lon": -4.0120},
    {"name": "Settat",           "lat": 33.0010,  "lon": -7.6166},
    {"name": "Khouribga",        "lat": 32.8811,  "lon": -6.9063},
    {"name": "Errachidia",       "lat": 31.9314,  "lon": -4.4244},
    {"name": "Laâyoune",         "lat": 27.1525,  "lon": -13.2003},
    {"name": "Al Hoceïma",       "lat": 35.2442,  "lon": -3.9317},
    {"name": "Essaouira",        "lat": 31.5125,  "lon": -9.7700},
    {"name": "Guelmim",          "lat": 28.9884,  "lon": -10.0633},
]

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
    files = sorted(READY_DIR.glob("tensor_live_*.npy"))
    if not files:
        raise FileNotFoundError(f"No .npy tensors found in {READY_DIR}")
    return files[-1]


def _load_normalisation_stats() -> Tuple[np.ndarray, np.ndarray]:
    stats = np.load(NORM_STATS, allow_pickle=True)
    mean = stats["mean"].astype(np.float32)
    std  = stats["std"].astype(np.float32)
    std  = np.where(std < 1e-6, 1.0, std)
    return mean, std


def _load_climatology(month_index: int) -> Tuple[np.ndarray, np.ndarray]:
    if not CLIMATOLOGY_FILE.exists():
        logger.warning(
            "%s not found — using fallback thresholds "
            "(tmax=45 °C, tmin=0 °C).  "
            "Run the climatology builder to populate real percentiles.",
            CLIMATOLOGY_FILE,
        )
        tmax_90p = np.full((37, 65), 45.0, dtype=np.float32)
        tmin_10p = np.full((37, 65),  0.0, dtype=np.float32)
        return tmax_90p, tmin_10p

    ds = xr.open_dataset(CLIMATOLOGY_FILE, engine="netcdf4")
    ds = ds.sel(latitude=slice(36, 27), longitude=slice(-17, -1))
    tmax_90p = ds["tmax_90p"].values.astype(np.float32)
    tmin_10p = ds["tmin_10p"].values.astype(np.float32)
    ds.close()
    return tmax_90p, tmin_10p


# ---------------------------------------------------------------------------
# NOAA Rothfusz Heat Index
# ---------------------------------------------------------------------------
def _noaa_heat_index(t_celsius: float, rh_percent: float) -> float:
    """
    NOAA Rothfusz regression for Heat Index.
    Converts Celsius to Fahrenheit, computes HI in °F, then back to °C.

    Reference: https://www.weather.gov/media/epz/wxcalc/heatIndex.pdf
    """
    if t_celsius < 26.7:
        return t_celsius

    t_f = t_celsius * 9.0 / 5.0 + 32.0
    rh = rh_percent

    hi_f = (-42.379
            + 2.04901523 * t_f
            + 10.14333127 * rh
            - 0.22475541 * t_f * rh
            - 6.83783e-3 * t_f ** 2
            - 5.481717e-2 * rh ** 2
            + 1.22874e-3 * t_f ** 2 * rh
            + 8.5282e-4 * t_f * rh ** 2
            - 1.99e-6 * t_f ** 2 * rh ** 2)

    if rh < 13.0 and 80.0 <= t_f <= 112.0:
        adjustment = ((13.0 - rh) / 4.0) * ((17.0 - abs(t_f - 95.0)) / 17.0) ** 0.5
        hi_f -= adjustment
    elif rh > 85.0 and 80.0 <= t_f <= 87.0:
        adjustment = ((rh - 85.0) / 10.0) * ((87.0 - t_f) / 5.0)
        hi_f += adjustment

    hi_c = (hi_f - 32.0) * 5.0 / 9.0
    return max(t_celsius, hi_c)


# ---------------------------------------------------------------------------
# Severity ↔ alert level
# ---------------------------------------------------------------------------
def _severity_to_alert_level(severity: float) -> str:
    if severity <= 0.0:
        return "none"
    if severity > 5.0:
        return "red"
    if severity > 2.0:
        return "orange"
    return "yellow"


# ---------------------------------------------------------------------------
# City-based GeoJSON builder
# ---------------------------------------------------------------------------
def _build_city_geojson(
    tmax_90p: np.ndarray,                  # [lat, lon]
    pred_tmax: np.ndarray,                 # [7, lat, lon]
    pred_tmin: np.ndarray,                 # [7, lat, lon]
    pred_rh: np.ndarray,                   # [7, lat, lon]
    latitudes: np.ndarray,                 # [lat,]
    longitudes: np.ndarray,                # [lon,]
) -> dict:
    """
    Build a lightweight GeoJSON FeatureCollection that contains one Feature
    per Moroccan city, each with its 7-day forecast payload.
    """
    start_date = datetime.utcnow()
    features = []

    for city in MOROCCO_CITIES:
        r = int(np.abs(latitudes - city["lat"]).argmin())
        c = int(np.abs(longitudes - city["lon"]).argmin())

        if np.isnan(tmax_90p[r, c]) or tmax_90p[r, c] < 5:
            continue

        day_forecasts = []
        max_severity = -999.0

        for d in range(7):
            tmax_val = float(pred_tmax[d, r, c])
            tmin_val = float(pred_tmin[d, r, c])
            rh_val   = float(pred_rh[d, r, c])

            hi_val = _noaa_heat_index(tmax_val, rh_val)

            severity = tmax_val - float(tmax_90p[r, c])
            if severity > max_severity:
                max_severity = severity

            day_alert = _severity_to_alert_level(severity)
            forecast_date = (start_date + timedelta(days=d)).strftime("%Y-%m-%d")

            day_forecasts.append({
                "day":         d,
                "date":        forecast_date,
                "tmax":        round(tmax_val, 1),
                "tmin":        round(tmin_val, 1),
                "rh":          round(rh_val, 1),
                "heat_index":  round(hi_val, 1),
                "severity":    round(max(0.0, severity), 1),
                "alert_level": day_alert,
            })

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [city["lon"], city["lat"]]},
            "properties": {
                "name":        city["name"],
                "alert_level": _severity_to_alert_level(max_severity),
                "severity":    round(max(0.0, max_severity), 1),
                "forecasts":   day_forecasts,
            },
        })

    logger.info("GeoJSON: %d city features built", len(features))
    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# Inference pipeline
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


def run_inference(tensor_path: Optional[Path] = None, device: str = "cpu") -> Path:
    if tensor_path is None:
        tensor_path = _find_latest_tensor()

    logger.info("=" * 60)
    logger.info("START Inference | tensor: %s", tensor_path.name)

    # ---- 1. Load model ----
    from models import Seq2SeqConvLSTM, CNN3D

    if MODEL_WEIGHTS.exists():
        raw_state = torch.load(MODEL_WEIGHTS, map_location=device)
        state = _extract_state_dict(raw_state)
        model_type = _infer_model_type(state)

        if model_type == "cnn3d":
            model = CNN3D(n_in=7, n_out=3, output_window=7)
        else:
            model = Seq2SeqConvLSTM(
                input_window=7, output_window=7,
                lat=37, lon=65, n_in=7, n_out=3,
                filters=64, kernel_size=3,
            )

        model.load_state_dict(state)
        logger.info("Loaded %s weights from %s", model_type, MODEL_WEIGHTS)
    else:
        logger.error(
            "Model weights NOT FOUND at %s — "
            "running with random initialization. Predictions are meaningless.",
            MODEL_WEIGHTS,
        )
        model = Seq2SeqConvLSTM(
            input_window=7, output_window=7,
            lat=37, lon=65, n_in=7, n_out=3,
            filters=64, kernel_size=3,
        )

    model.to(device)
    model.eval()

    # ---- 2. Load & prepare input tensor ----
    raw_tensor = np.load(tensor_path).astype(np.float32)
    logger.info("Loaded tensor shape: %s", raw_tensor.shape)

    tensor_tch = raw_tensor.transpose(0, 3, 1, 2)
    tensor_tch = torch.from_numpy(tensor_tch).unsqueeze(0).to(device)

    if tensor_tch.shape[1] > 7:
        tensor_tch = tensor_tch[:, -7:, ...]

    if tensor_tch.shape[1] != 7:
        logger.error("Expected 7 days in input tensor, got %d", tensor_tch.shape[1])
        raise ValueError("Input tensor must contain exactly 7 days")

    logger.info("Debug Input tensor: min=%.2f, max=%.2f, has_nan=%s",
                tensor_tch.min().item(), tensor_tch.max().item(),
                torch.isnan(tensor_tch).any().item())

    if tensor_tch.shape[-2:] != (37, 65):
        B, T, C, H, W = tensor_tch.shape
        tensor_tch = tensor_tch.view(B * T, C, H, W)
        import torch.nn.functional as F
        tensor_tch = F.interpolate(tensor_tch, size=(37, 65), mode='bilinear', align_corners=False)
        tensor_tch = tensor_tch.view(B, T, C, 37, 65)

    tensor_tch = torch.nan_to_num(tensor_tch, nan=0.0)

    # ---- 3. Forward pass ----
    with torch.no_grad():
        pred_norm = model(tensor_tch)          # [1, 7, 3, 37, 65]

    # ---- 4. Denormalise predictions ----
    mean_all, std_all = _load_normalisation_stats()
    mean_targ = torch.from_numpy(mean_all[:3]).view(1, 1, 3, 1, 1).to(device)
    std_targ  = torch.from_numpy(std_all[:3]).view(1, 1, 3, 1, 1).to(device)

    pred_phys = pred_norm * std_targ + mean_targ     # [1, 7, 3, 37, 65]
    pred_7d   = pred_phys[0].cpu().numpy()            # [7, 3, 37, 65]

    pred_tmax = pred_7d[:, 0, :, :]                   # [7, 37, 65]
    pred_tmin = pred_7d[:, 1, :, :]                   # [7, 37, 65]
    pred_rh   = pred_7d[:, 2, :, :]                   # [7, 37, 65]

    logger.info("Debug pred_tmax (mean across days): %.2f", pred_tmax.mean())

    # ---- 5. Climatology ----
    current_month = (datetime.utcnow() - timedelta(days=5)).month
    month_idx = current_month - 1

    tmax_90p, _ = _load_climatology(month_idx)
    logger.info("Debug tmax_90p mean: %.2f", tmax_90p.mean())

    # ---- 6. Build city GeoJSON ----
    lats = np.linspace(36, 27, 37, endpoint=True)
    lons = np.linspace(-17, -1, 65, endpoint=True)

    geojson = _build_city_geojson(
        tmax_90p=tmax_90p,
        pred_tmax=pred_tmax,
        pred_tmin=pred_tmin,
        pred_rh=pred_rh,
        latitudes=lats,
        longitudes=lons,
    )

    with open(OUTPUT_GEOJSON, "w") as fh:
        json.dump(geojson, fh, indent=2)

    logger.info("GeoJSON written → %s", OUTPUT_GEOJSON)
    logger.info("Inference completed successfully. %d cities output.",
                len(geojson["features"]))
    return OUTPUT_GEOJSON


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SAP Morocco — Inference & Alerting (City-based)")
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
