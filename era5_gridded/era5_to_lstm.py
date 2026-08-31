r"""
era5_to_lstm.py
================

Transforme le GeoTIFF ERA5 (Google Earth Engine) `data2/ERA5_Morocco_2023.tif`
en un format exploitable par nos modeles LSTM.

Le fichier .tif est une image multi-bandes :
    forme brute = (lat=153, lon=163, bandes=3276)
    3276 bandes = 364 jours * 9 variables  (interleaved : jour0_var0..jour0_var8, jour1_var0, ...)

On produit deux choses :

1. Un dataset TABULAIRE "long" (un point de grille = une "station"), identique
   dans l'esprit a `data/cleandata_gsod_by_station`. Colonnes :
       pixel_id, latitude, longitude, date, <features meteo + cibles>
   -> ce fichier .parquet se branche directement sur nos notebooks LSTM.

2. Une fonction `make_sequences(...)` qui montre que le LSTM prend bien des
   entrees de forme (batch_size, timesteps, n_features).

Variables ERA5 brutes (unites d'origine) et conversions appliquees :
    temperature_2m_max            K   -> tmax_c        (- 273.15)
    temperature_2m_min            K   -> tmin_c        (- 273.15)
    dewpoint_temperature_2m       K   -> dewp_c        (- 273.15)
    soil_temperature_level_1      K   -> soil_temp_c   (- 273.15)
    u_component_of_wind_10m       m/s ->  \  wind_speed_ms = sqrt(u^2+v^2)
    v_component_of_wind_10m       m/s ->  /  wind_dir_deg  (direction meteo)
    surface_pressure              Pa  -> press_hpa     (/ 100)
    surface_solar_radiation_..sum J/m2-> ssr_mj_m2     (/ 1e6)
    volumetric_soil_water_layer_1 m3/m3 -> soil_water  (tel quel)

Features derivees (memes formules que Data-collector-pfe/clean_gsod_data.py) :
    tmean_c       = (tmax_c + tmin_c) / 2
    humidity_pct  = August-Roche-Magnus a partir de (tmax_c, dewp_c)
    heat_index    = Rothfusz(tmax_c, humidity_pct)   [cible principale]
    wind_chill    = f(tmean_c, wind_speed_ms)

Usage CLI :
    python3 era5_gridded/era5_to_lstm.py \
        --tif data2/ERA5_Morocco_2023.tif \
        --out data2/era5_morocco_2023_long.parquet
"""

from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd
import tifffile

# ---------------------------------------------------------------------------
# 1. Lecture du GeoTIFF + metadonnees (dates / variables / geo-transform)
# ---------------------------------------------------------------------------

def read_era5_tif(tif_path: str):
    """Lit le .tif ERA5 et renvoie (cube, lats, lons, dates, var_names).

    cube  : ndarray float32 de forme (H, W, n_days, n_vars)
    lats  : ndarray (H,)   latitudes du centre de chaque ligne (nord -> sud)
    lons  : ndarray (W,)   longitudes du centre de chaque colonne (ouest -> est)
    dates : list[pd.Timestamp] (n_days,)
    var_names : list[str] (n_vars,)
    """
    with tifffile.TiffFile(tif_path) as tif:
        page = tif.pages[0]
        raw = page.asarray()  # (H, W, n_bands)
        md = page.tags["GDAL_METADATA"].value
        # geo-transform : origine (coin haut-gauche) + taille de pixel
        scale = page.tags["ModelPixelScaleTag"].value       # (sx, sy, sz)
        tie = page.tags["ModelTiepointTag"].value           # (i,j,k, X,Y,Z)

    H, W, n_bands = raw.shape

    # -- band descriptions : "YYYYMMDD_variable"
    root = ET.fromstring(md)
    descs = [it.text for it in root.findall(".//Item")
             if it.get("role") == "description"]
    dates_raw, vars_raw = [], []
    for d in descs:
        m = re.match(r"(\d{8})_(.+)", d)
        dates_raw.append(m.group(1))
        vars_raw.append(m.group(2))

    var_names = list(dict.fromkeys(vars_raw))               # ordre preserve
    n_vars = len(var_names)
    assert n_bands % n_vars == 0, "bandes non divisibles par le nb de variables"
    n_days = n_bands // n_vars

    unique_dates = list(dict.fromkeys(dates_raw))
    dates = [pd.Timestamp(d) for d in unique_dates]

    # -- reshape (H, W, n_days*n_vars) -> (H, W, n_days, n_vars)
    #    l'ordre des bandes est [jour, variable] donc reshape C-order direct.
    cube = raw.reshape(H, W, n_days, n_vars).astype(np.float32)

    # -- coordonnees lat/lon (centre de pixel)
    sx, sy = scale[0], scale[1]
    x0, y0 = tie[3], tie[4]          # coin haut-gauche
    lons = x0 + (np.arange(W) + 0.5) * sx
    lats = y0 - (np.arange(H) + 0.5) * sy   # y decroit vers le sud

    return cube, lats, lons, dates, var_names


# ---------------------------------------------------------------------------
# 2. Formules physiques (reprises de clean_gsod_data.py)
# ---------------------------------------------------------------------------

def relative_humidity(temp_c: np.ndarray, dewp_c: np.ndarray) -> np.ndarray:
    """RH (%) via August-Roche-Magnus, calculee a la temperature `temp_c`."""
    a, b = 17.625, 243.04
    es = 6.112 * np.exp((a * temp_c) / (b + temp_c))
    e = 6.112 * np.exp((a * dewp_c) / (b + dewp_c))
    return np.clip((e / es) * 100.0, 0.0, 100.0)


def heat_index_vec(temp_c: np.ndarray, rh: np.ndarray) -> np.ndarray:
    """Heat Index (Rothfusz) en Celsius, version vectorisee numpy.

    Equivalent a `calculate_heat_index` de clean_gsod_data.py mais applique
    sur des tableaux entiers (bien plus rapide que la boucle Python).
    """
    T = temp_c * 9.0 / 5.0 + 32.0     # -> Fahrenheit
    RH = rh

    # branche "chaude" (Rothfusz complet)
    c1, c2, c3 = -42.379, 2.04901523, 10.14333127
    c4, c5, c6 = -0.22475541, -0.00683783, -0.05481717
    c7, c8, c9 = 0.00122874, 0.00085282, -0.00000199
    hi_hot = (c1 + c2*T + c3*RH + c4*T*RH + c5*T*T + c6*RH*RH
              + c7*T*T*RH + c8*T*RH*RH + c9*T*T*RH*RH)

    # ajustements
    adj_dry = ((13 - RH) / 4.0) * np.sqrt(np.clip((17 - np.abs(T - 95)) / 17.0, 0, None))
    hi_hot = np.where((RH < 13) & (T >= 80) & (T <= 112), hi_hot - adj_dry, hi_hot)
    adj_wet = ((RH - 85) / 10.0) * ((87 - T) / 5.0)
    hi_hot = np.where((RH > 85) & (T >= 80) & (T <= 87), hi_hot + adj_wet, hi_hot)

    # branche "froide" (formule simple)
    hi_cold = 0.5 * (T + 61.0 + ((T - 68.0) * 1.2) + (RH * 0.094))

    HI = np.where(T < 80, hi_cold, hi_hot)
    return (HI - 32.0) * 5.0 / 9.0    # -> Celsius


def wind_chill_vec(temp_c: np.ndarray, wind_ms: np.ndarray) -> np.ndarray:
    """Wind Chill (Celsius) vectorise. Renvoie temp_c hors du domaine valide."""
    kmh = wind_ms * 3.6
    wc = (13.12 + 0.6215*temp_c - 11.37*np.power(kmh, 0.16)
          + 0.3965*temp_c*np.power(kmh, 0.16))
    return np.where((temp_c <= 10.0) & (kmh > 4.8), wc, temp_c)


def elevation_from_pressure(press_hpa: np.ndarray, temp_c: np.ndarray) -> np.ndarray:
    """Estime l'altitude (m) a partir de la pression de surface (formule hypsometrique).

    Le .tif ERA5 ne contient PAS de bande d'altitude (MNT). On la derive donc de
    la pression, qui decroit avec l'altitude (equation hypsometrique NOAA) :

        h = ((P0 / P)^(1/5.257) - 1) * (T + 273.15) / 0.0065

    avec P0 = 1013.25 hPa (pression au niveau de la mer). C'est une ESTIMATION
    statique par point de grille, pas une valeur de MNT topographique.
    """
    P0 = 1013.25
    return (np.power(P0 / press_hpa, 1.0 / 5.257) - 1.0) * (temp_c + 273.15) / 0.0065


# ---------------------------------------------------------------------------
# 3. Cube -> DataFrame long (un point de grille = une station)
# ---------------------------------------------------------------------------

# ordre attendu des variables ERA5 dans le cube (verifie a l'execution)
ERA5_VARS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "u_component_of_wind_10m",
    "v_component_of_wind_10m",
    "dewpoint_temperature_2m",
    "soil_temperature_level_1",
    "surface_solar_radiation_downwards_sum",
    "surface_pressure",
    "volumetric_soil_water_layer_1",
]


def cube_to_long(cube, lats, lons, dates, var_names) -> pd.DataFrame:
    """Convertit le cube (H,W,D,V) en DataFrame long, en enlevant l'ocean (NaN)."""
    idx = {v: i for i, v in enumerate(var_names)}
    for v in ERA5_VARS:
        assert v in idx, f"variable ERA5 manquante dans le .tif : {v}"

    H, W, D, V = cube.shape

    # masque des points de grille valides : un pixel est "terre" s'il n'est
    # pas NaN sur toute la serie (l'ocean est masque par GEE -> NaN partout).
    valid = ~np.isnan(cube[:, :, 0, idx["temperature_2m_max"]])   # (H, W)
    rows, cols = np.where(valid)
    n_pix = rows.size
    print(f"[cube_to_long] points terre = {n_pix} / {H*W} "
          f"({100*n_pix/(H*W):.1f}%), jours = {D}")

    def series(var):
        """(n_pix, D) serie temporelle du variable `var` pour les pixels valides."""
        return cube[rows, cols, :, idx[var]]   # fancy-index -> (n_pix, D)

    # --- variables brutes -> unites physiques
    tmax_c = series("temperature_2m_max") - 273.15
    tmin_c = series("temperature_2m_min") - 273.15
    dewp_c = series("dewpoint_temperature_2m") - 273.15
    soil_temp_c = series("soil_temperature_level_1") - 273.15
    u10 = series("u_component_of_wind_10m")
    v10 = series("v_component_of_wind_10m")
    press_hpa = series("surface_pressure") / 100.0
    ssr_mj = series("surface_solar_radiation_downwards_sum") / 1.0e6
    soil_water = series("volumetric_soil_water_layer_1")

    # --- derivees
    wind_speed_ms = np.sqrt(u10**2 + v10**2)
    wind_dir_deg = (np.degrees(np.arctan2(-u10, -v10))) % 360.0   # convention meteo
    tmean_c = (tmax_c + tmin_c) / 2.0
    humidity_pct = relative_humidity(tmax_c, dewp_c)
    heat_index = heat_index_vec(tmax_c, humidity_pct)
    wind_chill = wind_chill_vec(tmean_c, wind_speed_ms)

    # --- altitude statique par pixel (estimee depuis la pression, cf. formule)
    #     on prend la MEDIANE annuelle par pixel -> valeur stable, insensible
    #     aux passages depressionnaires, puis on la repete sur les D jours.
    elev_pix = elevation_from_pressure(np.median(press_hpa, axis=1),
                                       np.median(tmean_c, axis=1))   # (n_pix,)
    elev_pix = np.clip(elev_pix, 0.0, None)

    # --- coordonnees statiques par pixel, repetees sur les D jours
    pix_lat = lats[rows]                     # (n_pix,)
    pix_lon = lons[cols]
    pixel_id = rows * W + cols               # identifiant stable du point de grille

    lat_col = np.repeat(pix_lat, D)
    lon_col = np.repeat(pix_lon, D)
    elev_col = np.repeat(elev_pix, D)
    pid_col = np.repeat(pixel_id, D)
    date_col = np.tile(np.array(dates, dtype="datetime64[ns]"), n_pix)

    df = pd.DataFrame({
        "pixel_id": pid_col,
        "latitude": np.round(lat_col, 4),
        "longitude": np.round(lon_col, 4),
        "elevation": np.round(elev_col, 1),
        "date": date_col,
        "tmax_c": tmax_c.ravel(),
        "tmin_c": tmin_c.ravel(),
        "tmean_c": tmean_c.ravel(),
        "dewp_c": dewp_c.ravel(),
        "humidity_pct": humidity_pct.ravel(),
        "wind_speed_ms": wind_speed_ms.ravel(),
        "wind_dir_deg": wind_dir_deg.ravel(),
        "press_hpa": press_hpa.ravel(),
        "ssr_mj_m2": ssr_mj.ravel(),
        "soil_temp_c": soil_temp_c.ravel(),
        "soil_water": soil_water.ravel(),
        "heat_index": heat_index.ravel(),
        "wind_chill": wind_chill.ravel(),
    })

    # tri chronologique par pixel (indispensable pour les fenetres LSTM)
    df = df.sort_values(["pixel_id", "date"]).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# 4. DataFrame long -> tenseurs LSTM (batch_size, timesteps, n_features)
# ---------------------------------------------------------------------------

def make_sequences(
    df: pd.DataFrame,
    features: List[str],
    target: str = "heat_index",
    input_window: int = 7,
    output_window: int = 7,
    group_col: str = "pixel_id",
) -> Tuple[np.ndarray, np.ndarray]:
    """Construit des fenetres glissantes PAR point de grille.

    Renvoie :
        X : (n_samples, input_window, n_features)   <- entree LSTM
        y : (n_samples, output_window)              <- horizon a predire

    C'est exactement le format attendu par Keras :
    LSTM(input_shape=(input_window, n_features)).
    """
    Xs, ys = [], []
    feats = df[features].to_numpy(dtype=np.float32)
    tgt = df[target].to_numpy(dtype=np.float32)
    # bornes de chaque groupe (les lignes sont deja triees par groupe+date)
    codes = df[group_col].to_numpy()
    boundaries = np.flatnonzero(np.diff(codes)) + 1
    starts = np.concatenate(([0], boundaries))
    ends = np.concatenate((boundaries, [len(df)]))

    win = input_window + output_window
    for s, e in zip(starts, ends):
        n = e - s
        if n < win:
            continue
        for t in range(s, e - win + 1):
            Xs.append(feats[t:t + input_window])
            ys.append(tgt[t + input_window:t + win])
    if not Xs:
        return np.empty((0, input_window, len(features)), np.float32), \
               np.empty((0, output_window), np.float32)
    return np.stack(Xs), np.stack(ys)


# ---------------------------------------------------------------------------
# 5. CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="ERA5 GeoTIFF -> dataset LSTM")
    ap.add_argument("--tif", default="data2/ERA5_Morocco_2023.tif")
    ap.add_argument("--out", default="data2/era5_morocco_2023_long.parquet")
    ap.add_argument("--csv-sample", type=int, default=0,
                    help="si >0, ecrit aussi un CSV echantillon de N lignes")
    args = ap.parse_args()

    print(f"[read] {args.tif}")
    cube, lats, lons, dates, var_names = read_era5_tif(args.tif)
    print(f"[read] cube {cube.shape}  lat[{lats[0]:.2f}..{lats[-1]:.2f}]  "
          f"lon[{lons[0]:.2f}..{lons[-1]:.2f}]  jours {len(dates)}")

    df = cube_to_long(cube, lats, lons, dates, var_names)
    print(f"[long] DataFrame {df.shape}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"[save] {out}  ({out.stat().st_size/1e6:.1f} Mo)")

    if args.csv_sample > 0:
        sample = out.with_suffix(".sample.csv")
        df.head(args.csv_sample).to_csv(sample, index=False)
        print(f"[save] echantillon -> {sample}")

    # demonstration du format LSTM
    features = ["latitude", "longitude", "elevation", "tmax_c", "dewp_c",
                "humidity_pct", "wind_speed_ms", "press_hpa", "ssr_mj_m2",
                "soil_water", "heat_index"]
    demo = df[df["pixel_id"].isin(df["pixel_id"].unique()[:50])]
    X, y = make_sequences(demo, features, target="heat_index",
                          input_window=7, output_window=7)
    print(f"[lstm] X {X.shape} = (batch_size, timesteps, n_features)")
    print(f"[lstm] y {y.shape} = (batch_size, horizon)")


if __name__ == "__main__":
    main()
