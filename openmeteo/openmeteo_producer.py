"""
Open-Meteo station ingestion — SAP Morocco (Pipeline A).

Pulls the last N days of daily weather for each monitored GSOD station from the
free Open-Meteo API, rebuilds the *exact* feature schema the GRU model was
trained on (``data/cleandata_gsod_by_station/*_cleaned.csv``), and lands one CSV
per station on disk + (best-effort) in MinIO.

Design notes
------------
* **Rate limits.** Open-Meteo's free tier allows ~600 req/min / 5 000 req/hour /
  10 000 req/day (no key). We stay far under it by (a) packing many stations into
  each request via Open-Meteo's *multi-location* form (comma-separated lat/lon →
  a JSON array of results), (b) sleeping ``--min-interval`` between calls, and
  (c) exponential backoff that honours a ``429``'s ``Retry-After`` header.

* **Distribution match.** The model's inputs (``humidity_pct``, ``heat_index``,
  ``wind_chill``) are recomputed with the byte-for-byte formulas of
  ``Data-collector-pfe/clean_gsod_data.py`` — NOT Open-Meteo's own fields — so a
  live row is statistically the same object the model saw in training. Daily
  values follow GSOD (UTC) semantics: tmax/tmin from the daily API; tmean, dewp,
  wind, MSL pressure are hourly → daily means.

* **Static geo.** ``latitude``/``longitude``/``elevation`` come from the trained
  station registry (``openmeteo/stations.json``), not Open-Meteo, because those
  three are model *features* the scaler normalised against fixed values.

Usage
-----
    python openmeteo/openmeteo_producer.py --days 7
    python openmeteo/openmeteo_producer.py --days 7 --out data/live/openmeteo
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("openmeteo")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
# ERA5 reanalysis archive (real measured data, ~5-day latency) — used to backfill
# the gap between the GSOD archive's end and the live forecast window.
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY = Path(__file__).resolve().parent / "stations.json"

# Hourly vars we aggregate to daily means; daily vars we take as-is.
HOURLY_VARS = ["temperature_2m", "dew_point_2m", "wind_speed_10m", "pressure_msl"]
DAILY_VARS = ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"]

# Final CSV schema — identical to data/cleandata_gsod_by_station/*_cleaned.csv
OUT_COLUMNS = [
    "station_id", "station_name", "date", "latitude", "longitude", "elevation",
    "tmax_c", "tmin_c", "tmean_c", "dewp_c", "humidity_pct", "precip_mm",
    "wind_speed_ms", "press_hpa", "heat_index", "wind_chill",
]

# Magnus (August-Roche-Magnus) constants — match clean_gsod_data.py exactly.
_MA, _MB = 17.625, 243.04


# --------------------------------------------------------------------------- #
# Derived features — reproduced from Data-collector-pfe/clean_gsod_data.py
# --------------------------------------------------------------------------- #
def _rh_magnus(temp_c: np.ndarray, dewp_c: np.ndarray) -> np.ndarray:
    es = 6.112 * np.exp((_MA * temp_c) / (_MB + temp_c))
    e = 6.112 * np.exp((_MA * dewp_c) / (_MB + dewp_c))
    return np.clip((e / es) * 100.0, 0.0, 100.0)


def _heat_index(temp_c: float, rh: float) -> float:
    """Rothfusz Heat Index in °C (NWS), identical to clean_gsod_data.py."""
    if pd.isna(temp_c) or pd.isna(rh):
        return np.nan
    T = temp_c * 9 / 5 + 32
    RH = rh
    if T < 80:
        HI = 0.5 * (T + 61.0 + ((T - 68.0) * 1.2) + (RH * 0.094))
    else:
        HI = (-42.379 + 2.04901523 * T + 10.14333127 * RH - 0.22475541 * T * RH
              - 0.00683783 * T * T - 0.05481717 * RH * RH + 0.00122874 * T * T * RH
              + 0.00085282 * T * RH * RH - 0.00000199 * T * T * RH * RH)
        if RH < 13 and 80 <= T <= 112:
            HI -= ((13 - RH) / 4) * np.sqrt((17 - abs(T - 95)) / 17)
        elif RH > 85 and 80 <= T <= 87:
            HI += ((RH - 85) / 10) * ((87 - T) / 5)
    return (HI - 32) * 5 / 9


def _wind_chill(temp_c: float, wind_ms: float) -> float:
    """Metric NWS/EC Wind Chill in °C, identical to clean_gsod_data.py."""
    if pd.isna(temp_c) or pd.isna(wind_ms):
        return np.nan
    kmh = wind_ms * 3.6
    if temp_c <= 10.0 and kmh > 4.8:
        return (13.12 + 0.6215 * temp_c - 11.37 * (kmh ** 0.16)
                + 0.3965 * temp_c * (kmh ** 0.16))
    return temp_c


# --------------------------------------------------------------------------- #
# HTTP with polite rate limiting
# --------------------------------------------------------------------------- #
def _fetch(params: Dict[str, Any], *, min_interval: float, max_retries: int = 5,
           base_url: str = OPEN_METEO_URL) -> Any:
    """GET Open-Meteo with backoff; honours 429 Retry-After. Returns parsed JSON."""
    url = f"{base_url}?{urlencode(params, doseq=True)}"
    delay = 2.0
    for attempt in range(1, max_retries + 1):
        try:
            with urlopen(Request(url, headers={"User-Agent": "SAP-Morocco/1.0"}), timeout=60) as r:
                data = json.loads(r.read().decode())
            time.sleep(min_interval)  # be polite between successful calls
            return data
        except HTTPError as e:
            if e.code == 429:
                wait = float(e.headers.get("Retry-After", delay))
                logger.warning("429 rate-limited — sleeping %.0fs (attempt %d/%d)", wait, attempt, max_retries)
                time.sleep(wait)
                delay = min(delay * 2, 60)
                continue
            if 500 <= e.code < 600:
                logger.warning("HTTP %d — retry in %.0fs (attempt %d/%d)", e.code, delay, attempt, max_retries)
                time.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            raise
        except URLError as e:
            logger.warning("network error %s — retry in %.0fs (attempt %d/%d)", e.reason, delay, attempt, max_retries)
            time.sleep(delay)
            delay = min(delay * 2, 60)
    raise RuntimeError(f"Open-Meteo request failed after {max_retries} attempts: {url}")


# --------------------------------------------------------------------------- #
# Per-location daily table
# --------------------------------------------------------------------------- #
def _daily_frame(block: Dict[str, Any], today_utc: pd.Timestamp, keep_days: int) -> pd.DataFrame:
    """Turn one Open-Meteo result block into a GSOD-style daily frame."""
    # Hourly → daily means (UTC).
    hourly = pd.DataFrame(block["hourly"])
    hourly["date"] = pd.to_datetime(hourly["time"]).dt.floor("D")
    agg = hourly.groupby("date")[HOURLY_VARS].mean().rename(
        columns={
            "temperature_2m": "tmean_c",
            "dew_point_2m": "dewp_c",
            "wind_speed_10m": "wind_speed_ms",
            "pressure_msl": "press_hpa",
        }
    )
    # Daily API values.
    daily = pd.DataFrame(block["daily"])
    daily["date"] = pd.to_datetime(daily["time"])
    daily = daily.rename(columns={
        "temperature_2m_max": "tmax_c",
        "temperature_2m_min": "tmin_c",
        "precipitation_sum": "precip_mm",
    }).set_index("date")[["tmax_c", "tmin_c", "precip_mm"]]

    df = daily.join(agg, how="inner").reset_index()
    # Keep only complete past days (drop today's partial obs), then the last N.
    df = df[df["date"] < today_utc].sort_values("date").tail(keep_days)
    return df


def _finalize(df: pd.DataFrame, st: Dict[str, Any]) -> pd.DataFrame:
    """Attach static geo + derived features; enforce the output schema."""
    df = df.copy()
    df["station_id"] = st["station_id"]
    df["station_name"] = st["name"]
    df["latitude"] = st["lat"]
    df["longitude"] = st["lon"]
    df["elevation"] = st["elevation"]
    df["precip_mm"] = df["precip_mm"].fillna(0.0)

    # humidity at MEAN temp; heat index at MAX temp (RH recomputed at tmax).
    df["humidity_pct"] = _rh_magnus(df["tmean_c"].to_numpy(), df["dewp_c"].to_numpy())
    rh_at_tmax = _rh_magnus(df["tmax_c"].to_numpy(), df["dewp_c"].to_numpy())
    df["heat_index"] = [_heat_index(t, h) for t, h in zip(df["tmax_c"], rh_at_tmax)]
    df["wind_chill"] = [_wind_chill(t, w) for t, w in zip(df["tmin_c"], df["wind_speed_ms"])]

    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    return df[OUT_COLUMNS]


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def ingest(stations: List[Dict[str, Any]], days: int, out_dir: Path,
           chunk: int, min_interval: float, upload: bool) -> List[Path]:
    today_utc = pd.Timestamp(datetime.now(timezone.utc).date())
    out_dir.mkdir(parents=True, exist_ok=True)

    storage = None
    if upload:
        try:
            sys.path.insert(0, str(REPO_ROOT / "backend"))
            from app.core.storage import get_storage, RAW_PREFIX  # noqa
            storage = get_storage()
            if storage is None:
                logger.warning("MinIO unavailable — writing to disk only")
        except Exception as e:  # pragma: no cover
            logger.warning("MinIO helper not importable (%s) — disk only", e)

    written: List[Path] = []
    for i in range(0, len(stations), chunk):
        group = stations[i:i + chunk]
        params = {
            "latitude": [s["lat"] for s in group],
            "longitude": [s["lon"] for s in group],
            "past_days": days + 1,     # +1 so we still have N full days after dropping today
            "forecast_days": 1,
            "hourly": ",".join(HOURLY_VARS),
            "daily": ",".join(DAILY_VARS),
            "wind_speed_unit": "ms",
            "timezone": "UTC",
        }
        logger.info("Fetching stations %d–%d of %d …", i + 1, i + len(group), len(stations))
        result = _fetch(params, min_interval=min_interval)
        blocks = result if isinstance(result, list) else [result]  # multi- vs single-location

        for st, block in zip(group, blocks):
            try:
                daily = _daily_frame(block, today_utc, days)
                if len(daily) < days:
                    logger.warning("%s: only %d/%d days returned", st["code"], len(daily), days)
                out = _finalize(daily, st)
                path = out_dir / f"{st['code']}_cleaned.csv"
                out.to_csv(path, index=False)
                written.append(path)
                if storage is not None:
                    storage.upload_file(path, f"{RAW_PREFIX}stations/openmeteo/{st['code']}.csv")
                logger.info("%-16s %s → %s  HI=%.1f..%.1f",
                            st["code"], out["date"].iloc[0], out["date"].iloc[-1],
                            out["heat_index"].min(), out["heat_index"].max())
            except Exception:
                logger.exception("Failed to build %s", st["code"])
    return written


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Open-Meteo → GSOD-schema station ingestion.")
    ap.add_argument("--days", type=int, default=7, help="number of full past days to keep (model input window)")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "live" / "openmeteo")
    ap.add_argument("--registry", type=Path, default=REGISTRY)
    ap.add_argument("--chunk", type=int, default=10, help="stations per multi-location request")
    ap.add_argument("--min-interval", type=float, default=1.0, help="seconds to sleep between requests")
    ap.add_argument("--no-upload", action="store_true", help="skip the MinIO upload")
    args = ap.parse_args(argv)

    stations = json.loads(args.registry.read_text())
    logger.info("Ingesting %d full days for %d stations (chunk=%d, interval=%.1fs)",
                args.days, len(stations), args.chunk, args.min_interval)
    written = ingest(stations, args.days, args.out, args.chunk, args.min_interval, upload=not args.no_upload)
    logger.info("Wrote %d station CSVs → %s", len(written), args.out)
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
