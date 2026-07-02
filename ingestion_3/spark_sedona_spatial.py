"""
Stage 2 — spatialization with Apache Spark + Apache Sedona (the "big data" stage).

Turns the 30 station point-forecasts (Stage 1) into a continuous national risk
surface, using distributed Spatial SQL:

  1. Sedona generates an **H3 hexagon grid** covering Morocco (`ST_H3CellIDs`)
     and clips it to the national boundary (`ST_Intersects`).
  2. A distributed **k-nearest spatial join** (`ST_DistanceSphere`) links each
     hexagon to its nearest stations, and **IDW interpolation** (1/dᵖ) blends
     their 7-day forecasts — so every hexagon gets a smooth Heat Index / Wind
     Chill estimate even though only 30 stations were observed.
  3. Severity + alert level are computed per hexagon per day and written as the
     GeoJSON choropleth the 2D dashboard consumes.

Justification: the workload scales with the *resolution* of the surface
(10³–10⁶ hexes × 7 days × k-NN join), not the 30 stations — which is exactly
what Spark/Sedona are for.

Usage:
    python spark_sedona_spatial.py --h3-res 5 --k 4 --power 2
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from shapely.geometry import shape
from shapely.ops import unary_union

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
STATION_FC = PROJECT_ROOT / "data" / "processed" / "station_forecasts.geojson"
BOUNDARY = PROJECT_ROOT / "data" / "shapefiles" / "morocco" / "morocco.geojson"
OUT_PATH = PROJECT_ROOT / "public" / "data" / "today_alerts.geojson"

# Sedona jars (Spark 3.5 / Scala 2.12). Downloaded once into ~/.ivy2 at first run.
SEDONA_PKGS = ("org.apache.sedona:sedona-spark-shaded-3.5_2.12:1.7.1,"
               "org.datasyslab:geotools-wrapper:1.7.1-28.5")

HEAT_INDEX_ALERT_BASELINE_C = 32.0
WIND_CHILL_ALERT_BASELINE_C = 5.0

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                    stream=sys.stdout)
logger = logging.getLogger("Sedona-Spatial")


def _round_geom(geom: dict, ndigits: int = 4) -> dict:
    """Round GeoJSON coordinates to keep the file small (4 dp ≈ 11 m, well under
    a res-6 hexagon). Cuts the static file size by ~2-3x with no visible loss."""
    def r(x):
        if isinstance(x, (int, float)):
            return round(x, ndigits)
        return [r(v) for v in x]
    geom["coordinates"] = r(geom["coordinates"])
    return geom


def alert_level(sev: float) -> str:
    if sev <= 0.0:
        return "none"
    if sev > 5.0:
        return "red"
    if sev > 2.0:
        return "orange"
    return "yellow"


def _build_sedona(master: str):
    from sedona.spark import SedonaContext
    cfg = (SedonaContext.builder()
           .master(master)
           .appName("SAP-Sedona-Spatialization")
           .config("spark.jars.packages", SEDONA_PKGS)
           .config("spark.sql.shuffle.partitions", "8")
           .config("spark.ui.enabled", "false")
           .getOrCreate())
    cfg.sparkContext.setLogLevel("ERROR")
    return SedonaContext.create(cfg), cfg


def main() -> None:
    ap = argparse.ArgumentParser(description="Sedona spatialization (Stage 2)")
    ap.add_argument("--h3-res", type=int, default=5, help="H3 resolution (4 coarse .. 7 fine)")
    ap.add_argument("--k", type=int, default=4, help="nearest stations per hex (IDW)")
    ap.add_argument("--power", type=float, default=2.0, help="IDW power p (1/d^p)")
    ap.add_argument("--master", default="local[*]")
    ap.add_argument("--stations", default=str(STATION_FC))
    ap.add_argument("--boundary", default=str(BOUNDARY))
    ap.add_argument("--out", default=str(OUT_PATH))
    args = ap.parse_args()

    fc = json.loads(Path(args.stations).read_text())
    base_date = fc.get("base_date")
    horizon = int(fc.get("horizon", 7))
    feats = fc["features"]
    logger.info("Loaded %d station forecasts (base %s, horizon %d)", len(feats), base_date, horizon)

    # Long form: one row per (station, day) — the values IDW will interpolate.
    rows = []
    dates = None
    for f in feats:
        p = f["properties"]
        lon, lat = f["geometry"]["coordinates"]
        if dates is None:
            dates = [d["date"] for d in p["forecasts"]]
        for d in p["forecasts"]:
            rows.append((p["station"], int(d["day"]), float(lon), float(lat),
                         float(d["heat_index"]), float(d["wind_chill"])))

    # National boundary -> single WKT (union of the boundary parts).
    gj = json.loads(Path(args.boundary).read_text())
    geoms = [shape(ft["geometry"]) for ft in gj.get("features", [gj])]
    country_wkt = unary_union(geoms).wkt

    sedona, cfg = _build_sedona(args.master)
    try:
        from pyspark.sql import Row
        st = sedona.createDataFrame(
            [Row(station=r[0], day=r[1], lon=r[2], lat=r[3], hi=r[4], wc=r[5]) for r in rows])
        st.createOrReplaceTempView("st_raw")
        sedona.sql("SELECT *, ST_Point(lon, lat) AS geom FROM st_raw") \
              .createOrReplaceTempView("stations")

        sedona.createDataFrame([Row(wkt=country_wkt)]).createOrReplaceTempView("country_raw")
        sedona.sql("SELECT ST_GeomFromWKT(wkt) AS geom FROM country_raw") \
              .createOrReplaceTempView("country")

        # 1) H3 coverage of Morocco, clipped to the boundary.
        sedona.sql(f"SELECT explode(ST_H3CellIDs(geom, {args.h3_res}, true)) AS h3 FROM country") \
              .createOrReplaceTempView("hex_ids")
        # ST_H3ToGeom returns an ARRAY<geometry>; unwrap the single cell.
        sedona.sql("""
            SELECT hi.h3, element_at(ST_H3ToGeom(array(hi.h3)), 1) AS geom
            FROM hex_ids hi
        """).createOrReplaceTempView("hex_geom")
        sedona.sql("""
            SELECT h.h3,
                   ST_AsGeoJSON(h.geom) AS geojson,
                   ST_X(ST_Centroid(h.geom)) AS clon,
                   ST_Y(ST_Centroid(h.geom)) AS clat,
                   ST_Centroid(h.geom) AS centroid
            FROM hex_geom h JOIN country c ON ST_Intersects(h.geom, c.geom)
        """).createOrReplaceTempView("hexes")
        n_hex = sedona.table("hexes").count()
        logger.info("H3 res %d -> %d hexagons over Morocco", args.h3_res, n_hex)

        # 2) Distributed k-NN spatial join + IDW (per hexagon, per forecast day).
        sedona.sql("""
            SELECT h.h3, s.day, s.hi, s.wc,
                   ST_DistanceSphere(h.centroid, s.geom) AS dist
            FROM hexes h CROSS JOIN stations s
        """).createOrReplaceTempView("pairs")
        sedona.sql("""
            SELECT *, ROW_NUMBER() OVER (PARTITION BY h3, day ORDER BY dist) AS rn
            FROM pairs
        """).createOrReplaceTempView("ranked")
        idw = sedona.sql(f"""
            SELECT h3, day,
                   SUM(hi / POWER(dist + 1.0, {args.power})) / SUM(1.0 / POWER(dist + 1.0, {args.power})) AS hi,
                   SUM(wc / POWER(dist + 1.0, {args.power})) / SUM(1.0 / POWER(dist + 1.0, {args.power})) AS wc
            FROM ranked WHERE rn <= {args.k}
            GROUP BY h3, day
        """)

        # 3) Collect to driver and assemble the GeoJSON choropleth.
        meta = {r["h3"]: (r["geojson"], r["clon"], r["clat"])
                for r in sedona.table("hexes").select("h3", "geojson", "clon", "clat").collect()}
        per_hex: dict[int, list] = {}
        for r in idw.collect():
            per_hex.setdefault(r["h3"], []).append((int(r["day"]), float(r["hi"]), float(r["wc"])))

        # Compact per-hex schema: bare per-day arrays (hi/wc/sev/lvl) instead of
        # an array of {day,date,heat_index,...} objects. Avoids repeating JSON
        # keys 7×N times — shrinks a res-6 file ~4×. Dates live once, top-level.
        out_feats = []
        for h3, days in per_hex.items():
            geojson, clon, clat = meta[h3]
            hi_a, wc_a, sev_a, lvl_a, worst = [], [], [], [], -1e9
            for _day, hi, wc in sorted(days):
                sev = round(max(hi - HEAT_INDEX_ALERT_BASELINE_C,
                                WIND_CHILL_ALERT_BASELINE_C - wc), 2)
                worst = max(worst, sev)
                hi_a.append(round(hi, 1))
                wc_a.append(round(wc, 1))
                sev_a.append(sev)
                lvl_a.append(alert_level(sev))
            out_feats.append({
                "type": "Feature",
                "geometry": _round_geom(json.loads(geojson)),
                "properties": {"h3": str(h3), "lat": round(clat, 4), "lon": round(clon, 4),
                               "severity": round(worst, 2), "alert_level": alert_level(worst),
                               "hi": hi_a, "wc": wc_a, "sev": sev_a, "lvl": lvl_a},
            })

        out = {"type": "FeatureCollection", "model": fc.get("model"),
               "base_date": base_date, "horizon": horizon, "dates": dates,
               "method": f"sedona-h3r{args.h3_res}-idw-k{args.k}-p{args.power}",
               "features": out_feats}
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(out, separators=(",", ":")))
        logger.info("Wrote %d hex features -> %s", len(out_feats), out_path)
    finally:
        cfg.stop()


if __name__ == "__main__":
    main()
