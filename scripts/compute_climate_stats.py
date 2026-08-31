#!/usr/bin/env python3
"""
Compute long-term climate-change KPIs from NOAA GSOD station data.

Reads daily station files under data/noaa_gsod_by_station/<STATION>/<YEAR>.csv and
emits public/data/climate_stats.json, consumed by the analytics dashboard.

Method notes (engineering):
  * NOAA GSOD temperatures (TEMP/MAX/MIN) are in degrees Fahrenheit; sentinel for
    missing is 9999.9. We convert to Celsius and drop sentinels.
  * Stations enter/leave the record over time, so raw national averages would be
    biased by station composition. We therefore aggregate ANOMALIES: each station
    is compared to its own 1991-2020 baseline, then anomalies are averaged. Counts
    (heatwave days / warm nights) use per-station percentile thresholds, which are
    likewise station-relative.

Usage:
    python scripts/compute_climate_stats.py
"""

from __future__ import annotations

import csv
import glob
import json
import os
from collections import defaultdict
from datetime import datetime, timezone

# --------------------------------------------------------------------------
# Paths & constants
# --------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "noaa_gsod_by_station")
OUT_PATH = os.path.join(ROOT, "public", "data", "climate_stats.json")

BASELINE_START, BASELINE_END = 1991, 2020  # WMO standard normal period
SENTINEL = 999.0  # any |°F| >= this is treated as missing
MIN_DAYS_YEAR = 200   # min valid days to use a station-year for annual metrics
MIN_DAYS_JJA = 60     # min valid summer days (Jun-Aug has 92)
MIN_BASELINE_YEARS = 10  # min baseline years for a station to be eligible


def f_to_c(f: float) -> float:
    return (f - 32.0) * 5.0 / 9.0


def percentile(sorted_vals: list[float], q: float) -> float:
    """Linear-interpolated percentile, q in [0,1]. Assumes sorted input."""
    if not sorted_vals:
        return float("nan")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def linregress_slope(xs: list[float], ys: list[float]) -> float:
    """Ordinary least-squares slope of y on x."""
    n = len(xs)
    if n < 2:
        return float("nan")
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    return num / den if den else float("nan")


# --------------------------------------------------------------------------
# Per-station daily record
# --------------------------------------------------------------------------
class StationYear:
    __slots__ = ("tmax", "tmin")

    def __init__(self) -> None:
        self.tmax: list[tuple[int, float]] = []  # (month, value_c)
        self.tmin: list[tuple[int, float]] = []


def load_station(station_dir: str) -> dict[int, StationYear]:
    """Return {year: StationYear} for one station."""
    by_year: dict[int, StationYear] = defaultdict(StationYear)
    for path in sorted(glob.glob(os.path.join(station_dir, "*.csv"))):
        with open(path, newline="") as fh:
            for row in csv.DictReader(fh):
                date = row.get("DATE", "")
                if len(date) < 7:
                    continue
                year = int(date[:4])
                month = int(date[5:7])
                sy = by_year[year]
                try:
                    mx = float(row["MAX"])
                    if abs(mx) < SENTINEL:
                        sy.tmax.append((month, f_to_c(mx)))
                except (KeyError, ValueError):
                    pass
                try:
                    mn = float(row["MIN"])
                    if abs(mn) < SENTINEL:
                        sy.tmin.append((month, f_to_c(mn)))
                except (KeyError, ValueError):
                    pass
    return by_year


def station_meta(station_dir: str) -> dict:
    """Pull name/coords from the most recent file's first row."""
    files = sorted(glob.glob(os.path.join(station_dir, "*.csv")))
    for path in reversed(files):
        with open(path, newline="") as fh:
            row = next(csv.DictReader(fh), None)
        if row:
            name = row.get("NAME", "").split(",")[0].title()
            try:
                return {"name": name, "lat": float(row["LATITUDE"]),
                        "lon": float(row["LONGITUDE"])}
            except (KeyError, ValueError):
                return {"name": name}
    return {}


# --------------------------------------------------------------------------
# Main computation
# --------------------------------------------------------------------------
def main() -> None:
    stations = sorted(
        d for d in os.listdir(DATA_DIR)
        if os.path.isdir(os.path.join(DATA_DIR, d))
    )

    # Per year -> lists of per-station values (for national averaging)
    tmax_anom: dict[int, list[float]] = defaultdict(list)
    jja_anom: dict[int, list[float]] = defaultdict(list)
    heatwave: dict[int, list[float]] = defaultdict(list)
    warm_nights: dict[int, list[float]] = defaultdict(list)
    raw_tmax: dict[int, list[float]] = defaultdict(list)

    used_stations = 0
    min_year, max_year = 9999, 0

    for st in stations:
        by_year = load_station(os.path.join(DATA_DIR, st))
        if not by_year:
            continue

        # ---- Build baseline (1991-2020) for this station ----
        base_annual_tx: list[float] = []   # per-year annual mean Tmax
        base_jja_tx: list[float] = []      # per-year JJA mean Tmax
        base_tx_all: list[float] = []      # all daily Tmax (for p90)
        base_tn_all: list[float] = []      # all daily Tmin (for p90)

        for yr in range(BASELINE_START, BASELINE_END + 1):
            sy = by_year.get(yr)
            if not sy:
                continue
            tx = [v for _, v in sy.tmax]
            if len(tx) >= MIN_DAYS_YEAR:
                base_annual_tx.append(sum(tx) / len(tx))
            jja = [v for m, v in sy.tmax if 6 <= m <= 8]
            if len(jja) >= MIN_DAYS_JJA:
                base_jja_tx.append(sum(jja) / len(jja))
            base_tx_all.extend(tx)
            base_tn_all.extend(v for _, v in sy.tmin)

        if len(base_annual_tx) < MIN_BASELINE_YEARS:
            continue  # not enough baseline to anchor anomalies

        baseline_tx = sum(base_annual_tx) / len(base_annual_tx)
        baseline_jja = (sum(base_jja_tx) / len(base_jja_tx)) if base_jja_tx else None
        base_tx_all.sort()
        base_tn_all.sort()
        tx90 = percentile(base_tx_all, 0.90)
        tn90 = percentile(base_tn_all, 0.90)

        used_stations += 1

        # ---- Per-year metrics relative to this station's baseline ----
        for yr, sy in by_year.items():
            tx = [v for _, v in sy.tmax]
            tn = [v for _, v in sy.tmin]
            min_year = min(min_year, yr)
            max_year = max(max_year, yr)

            if len(tx) >= MIN_DAYS_YEAR:
                mean_tx = sum(tx) / len(tx)
                tmax_anom[yr].append(mean_tx - baseline_tx)
                raw_tmax[yr].append(mean_tx)
                heatwave[yr].append(sum(1 for v in tx if v > tx90))

            jja = [v for m, v in sy.tmax if 6 <= m <= 8]
            if baseline_jja is not None and len(jja) >= MIN_DAYS_JJA:
                jja_anom[yr].append((sum(jja) / len(jja)) - baseline_jja)

            if len(tn) >= MIN_DAYS_YEAR:
                warm_nights[yr].append(sum(1 for v in tn if v > tn90))

    # ---- National series (mean across stations per year) ----
    years = sorted(y for y in tmax_anom if tmax_anom[y])

    def avg(d: dict[int, list[float]], y: int) -> float | None:
        vals = d.get(y)
        return round(sum(vals) / len(vals), 2) if vals else None

    series = {
        "years": years,
        "tmax_anomaly_c": [avg(tmax_anom, y) for y in years],
        "annual_mean_tmax_c": [avg(raw_tmax, y) for y in years],
        "summer_anomaly_c": [avg(jja_anom, y) for y in years],
        "heatwave_days": [round(avg(heatwave, y) or 0) for y in years],
        "warm_nights": [round(avg(warm_nights, y) or 0) for y in years],
    }

    # ---- Headline KPIs ----
    anom_pairs = [(y, avg(tmax_anom, y)) for y in years]
    anom_pairs = [(y, a) for y, a in anom_pairs if a is not None]
    slope = linregress_slope([y for y, _ in anom_pairs], [a for _, a in anom_pairs])
    warming_per_decade = round(slope * 10, 2) if slope == slope else None

    latest = years[-1] if years else None
    kpis = {
        "warming_rate_c_per_decade": warming_per_decade,
        "latest_year": latest,
        "latest_summer_anomaly_c": avg(jja_anom, latest) if latest else None,
        "heatwave_days_latest": (series["heatwave_days"][-1] if years else None),
        "warm_nights_latest": (series["warm_nights"][-1] if years else None),
    }

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "NOAA GSOD",
        "baseline_period": f"{BASELINE_START}-{BASELINE_END}",
        "n_stations": used_stations,
        "year_range": [min_year, max_year],
        "kpis": kpis,
        "series": series,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as fh:
        json.dump(out, fh, indent=2)

    print(f"Wrote {OUT_PATH}")
    print(f"  stations used: {used_stations}/{len(stations)}")
    print(f"  years: {min_year}-{max_year}")
    print(f"  warming rate: {warming_per_decade} °C/decade")
    print(f"  latest ({latest}) summer anomaly: {kpis['latest_summer_anomaly_c']} °C")
    print(f"  heatwave days {latest}: {kpis['heatwave_days_latest']}")
    print(f"  warm nights {latest}: {kpis['warm_nights_latest']}")


if __name__ == "__main__":
    main()
