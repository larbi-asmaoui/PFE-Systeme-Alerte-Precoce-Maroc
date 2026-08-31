"""
Offline station forecaster — SAP Morocco.

Runs the trained **GRU** model over the cleaned GSOD station histories in
``data/cleandata_gsod_by_station`` and writes a static GeoJSON that the Next.js
dashboard consumes (one Point feature per station, each with a 7-day Heat Index /
Wind Chill forecast + alert levels).

This is a *batch* job: it is executed on demand (or from a cron / Airflow DAG),
never inside the FastAPI request path, so the API image stays free of TensorFlow.

Pipeline (per station)
----------------------
    last 7 daily rows  ->  scaler_X.transform  ->  GRU.predict -> (7, 2)
                       ->  inverse z-score with scaler_X stats
                       ->  felt_severity / alert level (shared with the API)

Why inverse with ``scaler_X``?
    ``heat_index`` and ``wind_chill`` are *both* input features and targets. The
    model was trained on the standardized targets (there is no separate
    ``scaler_y``), so each predicted channel is un-scaled with the mean/std that
    ``scaler_X`` learned for that same column.

Usage
-----
    python backend/predict_stations.py \
        --stations   data/cleandata_gsod_by_station \
        --artifacts  "lstm_testing_noaa_gsod_by_station_new-20260710T085419Z-2-001/lstm_testing_noaa_gsod_by_station_new" \
        --out        public/data/stations_forecast.geojson
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")  # hush TensorFlow banners

import joblib
import numpy as np
import pandas as pd

# Shared, torch-free severity helpers (also used by the /alerts API).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.core.meteo import (  # noqa: E402
    FORECAST_HORIZON,
    felt_severity,
    severity_to_alert_level,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("predict_stations")

# Target channels produced by the model, in order.
TARGETS = ["heat_index", "wind_chill"]
INPUT_WINDOW = 7


def load_bundle(artifacts: Path):
    """Load the GRU model and the fitted feature scaler.

    Returns ``(model, scaler, features, target_idx)`` where ``target_idx`` maps
    each target name to its column position inside the scaler's feature space.
    """
    import keras  # imported lazily so `--help` works without TF installed

    model_path = artifacts / "models" / "GRU.keras"
    scaler_path = artifacts / "scaler_X.pkl"
    if not model_path.exists():
        raise FileNotFoundError(f"GRU model not found: {model_path}")
    if not scaler_path.exists():
        raise FileNotFoundError(f"Scaler not found: {scaler_path}")

    model = keras.saving.load_model(str(model_path), compile=False)
    scaler = joblib.load(scaler_path)  # joblib pickle, not plain pickle
    features = list(scaler.feature_names_in_)
    target_idx = {t: features.index(t) for t in TARGETS}

    in_shape = tuple(model.input_shape)
    if in_shape[1:] != (INPUT_WINDOW, len(features)):
        raise ValueError(
            f"Model input {in_shape} does not match "
            f"(*, {INPUT_WINDOW}, {len(features)}) implied by the scaler"
        )
    logger.info("Loaded GRU %s -> %s | %d features", in_shape, model.output_shape, len(features))
    return model, scaler, features, target_idx


def impute_pressure(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing ``press_hpa`` from ``elevation`` via the barometric formula.

    Some stations (e.g. HAS1, CHE_MOULAY) never reported surface pressure. We
    estimate it from the ISA standard atmosphere so the station still gets a
    forecast: ``P = 1013.25 * (1 - 2.25577e-5 * h) ** 5.25588`` (h in metres).
    """
    if "press_hpa" not in df.columns or "elevation" not in df.columns:
        return df
    missing = df["press_hpa"].isna()
    if not missing.any():
        return df
    h = df.loc[missing, "elevation"].astype(float)
    df.loc[missing, "press_hpa"] = 1013.25 * (1.0 - 2.25577e-5 * h) ** 5.25588
    return df


def station_window(csv_path: Path, features: List[str]) -> pd.DataFrame | None:
    """Return the last ``INPUT_WINDOW`` valid daily rows for a station, or None."""
    df = pd.read_csv(csv_path, parse_dates=["date"])
    df = impute_pressure(df)
    df = df.sort_values("date").dropna(subset=features)
    if len(df) < INPUT_WINDOW:
        logger.warning("Skipping %s — only %d usable rows", csv_path.name, len(df))
        return None
    return df.tail(INPUT_WINDOW)


def forecast_station(model, scaler, features, target_idx, window: pd.DataFrame) -> Dict[str, Any]:
    """Run the model on one station window and return its forecast payload."""
    # Pass a DataFrame (not .values) so the scaler keeps its feature names.
    x = scaler.transform(window[features]).astype("float32")[None, ...]  # (1, 7, F)
    pred = model.predict(x, verbose=0)[0]  # (7, 2), standardized

    hi = pred[:, 0] * scaler.scale_[target_idx["heat_index"]] + scaler.mean_[target_idx["heat_index"]]
    wc = pred[:, 1] * scaler.scale_[target_idx["wind_chill"]] + scaler.mean_[target_idx["wind_chill"]]

    sev = [float(felt_severity(float(h), float(c))) for h, c in zip(hi, wc)]
    lvl = [severity_to_alert_level(s) for s in sev]

    last_obs = window["date"].iloc[-1]
    dates = [(last_obs + timedelta(days=d + 1)).strftime("%Y-%m-%d") for d in range(FORECAST_HORIZON)]

    row = window.iloc[-1]
    worst = int(np.argmax(sev))
    return {
        "station_id": str(row.get("station_id", "")),
        "station_name": str(row.get("station_name", "")),
        "lat": float(row["latitude"]),
        "lon": float(row["longitude"]),
        "elevation": float(row["elevation"]),
        "last_obs_date": last_obs.strftime("%Y-%m-%d"),
        "dates": dates,
        "hi": [round(float(v), 2) for v in hi],
        "wc": [round(float(v), 2) for v in wc],
        "sev": [round(s, 2) for s in sev],
        "lvl": lvl,
        "severity": round(sev[worst], 2),      # worst day over the horizon
        "alert_level": lvl[worst],
    }


def build_geojson(stations_dir: Path, artifacts: Path) -> Dict[str, Any]:
    model, scaler, features, target_idx = load_bundle(artifacts)

    csvs = sorted(stations_dir.glob("*_cleaned.csv"))
    if not csvs:
        raise FileNotFoundError(f"No *_cleaned.csv files in {stations_dir}")

    features_present = features  # already validated against the scaler
    feats: List[Dict[str, Any]] = []
    for csv_path in csvs:
        window = station_window(csv_path, features_present)
        if window is None:
            continue
        payload = forecast_station(model, scaler, features, target_idx, window)
        feats.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [payload["lon"], payload["lat"]]},
                "properties": payload,
            }
        )
        logger.info(
            "%-28s %s  HI=%.1f..%.1f  lvl=%s",
            payload["station_name"] or csv_path.stem,
            payload["last_obs_date"],
            min(payload["hi"]),
            max(payload["hi"]),
            payload["alert_level"],
        )

    # Collection-level forecast dates (from the most recent station window) so the
    # dashboard's day-slider can label days uniformly, exactly like today_alerts.
    dates: List[str] = []
    if feats:
        latest = max(feats, key=lambda f: f["properties"]["last_obs_date"])
        dates = latest["properties"]["dates"]

    return {
        "type": "FeatureCollection",
        "dates": dates,
        "properties": {
            "model": "GRU",
            "input_window": INPUT_WINDOW,
            "forecast_horizon": FORECAST_HORIZON,
            "targets": TARGETS,
            "n_stations": len(feats),
        },
        "features": feats,
    }


def main(argv: List[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description="Offline GSOD station forecaster (GRU).")
    ap.add_argument("--stations", type=Path, default=repo_root / "data" / "cleandata_gsod_by_station")
    ap.add_argument(
        "--artifacts",
        type=Path,
        default=repo_root
        / "lstm_testing_noaa_gsod_by_station_new-20260710T085419Z-2-001"
        / "lstm_testing_noaa_gsod_by_station_new",
    )
    ap.add_argument("--out", type=Path, default=repo_root / "public" / "data" / "stations_forecast.geojson")
    args = ap.parse_args(argv)

    fc = build_geojson(args.stations, args.artifacts)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(fc, fh, ensure_ascii=False, separators=(",", ":"))
    logger.info("Wrote %d station forecasts -> %s", fc["properties"]["n_stations"], args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
