"""
Stage 1 — station nowcast (lightweight TensorFlow inference).

Loads the best temporal model trained in `temporal_training/` (per
`lstm_meta.json`), takes the last `input_window` days for each of the 30
stations, and predicts the next `output_window` days of HeatIndex / WindChill.
Severity + alert level are derived exactly like the backend
(`backend/app/core/meteo.py`).

Output: `data/processed/station_forecasts.geojson` — one **Point** feature per
station carrying the full multi-day forecast. This is the small, fast input the
Spark/Sedona spatialization stage interpolates into a national risk surface.

No Spark here on purpose: 30 stations x 7 days is kilobytes — a single-process
TF job runs in seconds. Usage:

    python predict_stations.py
    python predict_stations.py --data-dir data/ml_final_merged_csv --model GRU
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import timedelta
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
ART_DIR = PROJECT_ROOT / "temporal_training" / "artifacts"
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "ml_final_merged_csv"
OUT_PATH = PROJECT_ROOT / "data" / "processed" / "station_forecasts.geojson"

# Alert thresholds — kept in sync with backend/app/core/meteo.py (single source of truth).
HEAT_INDEX_ALERT_BASELINE_C = 32.0
WIND_CHILL_ALERT_BASELINE_C = 5.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("Station-Nowcast")


def felt_severity(heat_index: float, wind_chill: float) -> float:
    """°C into the alert zone — worst of heat stress and cold stress."""
    return float(max(heat_index - HEAT_INDEX_ALERT_BASELINE_C,
                     WIND_CHILL_ALERT_BASELINE_C - wind_chill))


def severity_to_alert_level(severity: float) -> str:
    if severity <= 0.0:
        return "none"
    if severity > 5.0:
        return "red"
    if severity > 2.0:
        return "orange"
    return "yellow"


def _load_meta() -> dict:
    return json.loads((ART_DIR / "lstm_meta.json").read_text())


def _load_model(meta: dict, override: Optional[str]):
    from tensorflow import keras  # imported here so --help is instant
    name = override or meta.get("best_model")
    candidates = [ART_DIR / "models" / f"{name}.keras", ART_DIR / "lstm_nasa_power.keras"]
    for path in candidates:
        if path.exists():
            logger.info("Loading model %s", path)
            return keras.models.load_model(str(path)), name
    raise FileNotFoundError(f"No model found among {candidates}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Station nowcast (Stage 1)")
    ap.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    ap.add_argument("--model", help="override best_model (e.g. GRU, LSTM, TCN)")
    ap.add_argument("--out", default=str(OUT_PATH))
    ap.add_argument("--base-date",
                    help="issue the forecast as-of this date (YYYY-MM-DD): use the "
                         "input window ending at the latest row <= base-date. "
                         "Default = last available row. Use a summer date to get a "
                         "seasonally-correct heat forecast until live ingestion is wired.")
    args = ap.parse_args()
    base_date = pd.Timestamp(args.base_date) if args.base_date else None

    meta = _load_meta()
    features = meta["features"]
    targets = meta["targets"]
    win_in = int(meta["input_window"])
    win_out = int(meta["output_window"])
    logger.info("features=%d targets=%s in=%d out=%d", len(features), targets, win_in, win_out)

    model, model_name = _load_model(meta, args.model)
    scaler_X = joblib.load(ART_DIR / "scaler_X.pkl")
    scaler_y = joblib.load(ART_DIR / "scaler_y.pkl")

    data_dir = Path(args.data_dir)
    files = sorted(data_dir.glob("*.csv"))
    if not files:
        raise SystemExit(f"No station CSVs in {data_dir}")

    features_out = []
    for f in files:
        df = pd.read_csv(f, parse_dates=["date"]).sort_values("date")
        df = df.replace(-999.0, np.nan).interpolate().ffill().bfill()
        if base_date is not None:
            df = df[df["date"] <= base_date]
        if len(df) < win_in:
            logger.warning("  %s: only %d rows (<%d) — skipped", f.stem, len(df), win_in)
            continue

        window = df.iloc[-win_in:]
        last_date = window["date"].iloc[-1]
        lat = float(window["latitude"].iloc[-1])
        lon = float(window["longitude"].iloc[-1])
        elev = float(window["elevation_m"].iloc[-1])

        X = scaler_X.transform(window[features])                  # keep feature names -> no warning
        X = X.astype(np.float32).reshape(1, win_in, len(features))
        pred = model.predict(X, verbose=0)[0]                     # [win_out, n_targets] scaled
        pred = scaler_y.inverse_transform(pred)                   # physical units

        forecasts, worst = [], -1e9
        for d in range(win_out):
            hi = float(pred[d, targets.index("HeatIndex")])
            wc = float(pred[d, targets.index("WindChill")])
            sev = round(felt_severity(hi, wc), 2)
            worst = max(worst, sev)
            forecasts.append({
                "day": d,
                "date": str((last_date + timedelta(days=d + 1)).date()),
                "heat_index": round(hi, 1),
                "wind_chill": round(wc, 1),
                "severity": sev,
                "alert_level": severity_to_alert_level(sev),
            })

        features_out.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "station": f.stem.replace("_final", ""),
                "lat": lat, "lon": lon, "elevation_m": elev,
                "severity": round(worst, 2),
                "alert_level": severity_to_alert_level(worst),
                "forecasts": forecasts,
            },
        })
        logger.info("  %-22s worst sev %.2f (%s)", f.stem.replace("_final", ""),
                    worst, severity_to_alert_level(worst))

    fc = {"type": "FeatureCollection", "model": model_name,
          "base_date": str(last_date.date()), "horizon": win_out, "features": features_out}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fc))
    logger.info("Wrote %d station forecasts -> %s", len(features_out), out_path)


if __name__ == "__main__":
    main()
