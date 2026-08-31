"""
Open-Meteo **archive** backfill — SAP Morocco (Pipeline A).

Fills the real gap between the GSOD archive's end (~2025-08-24) and the live
forecast window (last 7 days) with ERA5 *reanalysis* data from Open-Meteo's
historical archive API. This is measured data (not a forecast, not synthetic),
so the station-history "recent" chart becomes a continuous real series instead
of a straight line drawn across an empty gap.

It reuses the exact aggregation + feature formulas of ``openmeteo_producer.py``
so every backfilled row is the same statistical object the GRU model saw in
training. Output CSVs (``data/live/openmeteo_gap/<code>_cleaned.csv``) share the
GSOD schema and are merged by ``scripts/build_station_history.py``.

Rate limits: the archive API is a separate quota from the forecast endpoint; we
still pack stations into multi-location requests and sleep ``--min-interval``
between calls with the same 429-aware backoff.

Usage
-----
    python openmeteo/backfill_openmeteo.py --start 2025-08-01
    python openmeteo/backfill_openmeteo.py --start 2025-08-01 --end 2026-07-05
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from openmeteo_producer import (
    DAILY_VARS,
    HOURLY_VARS,
    OPEN_METEO_ARCHIVE_URL,
    REGISTRY,
    REPO_ROOT,
    _daily_frame,
    _fetch,
    _finalize,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("openmeteo.backfill")

KEEP_ALL = 10_000_000  # reuse _daily_frame but keep every day in the range


def backfill(stations: List[Dict[str, Any]], start: str, end: str, out_dir: Path,
             chunk: int, min_interval: float) -> List[Path]:
    today_utc = pd.Timestamp(datetime.now(timezone.utc).date())
    out_dir.mkdir(parents=True, exist_ok=True)

    written: List[Path] = []
    for i in range(0, len(stations), chunk):
        group = stations[i:i + chunk]
        params = {
            "latitude": [s["lat"] for s in group],
            "longitude": [s["lon"] for s in group],
            "start_date": start,
            "end_date": end,
            "hourly": ",".join(HOURLY_VARS),
            "daily": ",".join(DAILY_VARS),
            "wind_speed_unit": "ms",
            "timezone": "UTC",
        }
        logger.info("Archive %s→%s for stations %d–%d of %d …", start, end, i + 1, i + len(group), len(stations))
        result = _fetch(params, min_interval=min_interval, base_url=OPEN_METEO_ARCHIVE_URL)
        blocks = result if isinstance(result, list) else [result]

        for st, block in zip(group, blocks):
            try:
                daily = _daily_frame(block, today_utc, KEEP_ALL)
                if daily.empty:
                    logger.warning("%s: archive returned no usable days", st["code"])
                    continue
                out = _finalize(daily, st)
                path = out_dir / f"{st['code']}_cleaned.csv"
                out.to_csv(path, index=False)
                written.append(path)
                logger.info("%-16s %s → %s  (%d days)  HI=%.1f..%.1f",
                            st["code"], out["date"].iloc[0], out["date"].iloc[-1], len(out),
                            out["heat_index"].min(), out["heat_index"].max())
            except Exception:
                logger.exception("Failed to backfill %s", st["code"])
    return written


def main(argv: List[str] | None = None) -> int:
    yesterday = (pd.Timestamp(datetime.now(timezone.utc).date()) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Open-Meteo archive (ERA5) gap backfill → GSOD schema.")
    ap.add_argument("--start", default="2025-08-01", help="first day to backfill (YYYY-MM-DD)")
    ap.add_argument("--end", default=yesterday, help="last day to backfill (default: yesterday UTC)")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "live" / "openmeteo_gap")
    ap.add_argument("--registry", type=Path, default=REGISTRY)
    ap.add_argument("--chunk", type=int, default=10, help="stations per multi-location request")
    ap.add_argument("--min-interval", type=float, default=1.0, help="seconds to sleep between requests")
    args = ap.parse_args(argv)

    stations = json.loads(args.registry.read_text())
    logger.info("Backfilling %s→%s for %d stations (chunk=%d, interval=%.1fs)",
                args.start, args.end, len(stations), args.chunk, args.min_interval)
    written = backfill(stations, args.start, args.end, args.out, args.chunk, args.min_interval)
    logger.info("Wrote %d backfill CSVs → %s", len(written), args.out)
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
