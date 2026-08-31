# ERA5 gridded → LSTM

Transformation des données **ERA5 (Google Earth Engine)** `data2/ERA5_Morocco_2023.tif`
vers un format exploitable par nos modèles LSTM.

## Le fichier `.tif`

| propriété | valeur |
|---|---|
| forme brute | `(lat=153, lon=163, bandes=3276)` |
| grille | 0.1° (~11 km), WGS84 / EPSG:4326 |
| étendue | lat 20.75 → 35.95 N, lon -17.15 → -0.95 |
| période | quotidien, 2023-01-01 → 2023-12-30 (**364 jours**) |
| bandes | `3276 = 364 jours × 9 variables`, nommées `YYYYMMDD_variable` |
| ordre | interleaved : `jour0_var0..jour0_var8, jour1_var0, ...` |
| masque | ~74.5 % des pixels sont NaN (océan / hors-Maroc) → **6350 points terre** |

Les 9 variables ERA5 (unités brutes → conversions appliquées) :

| bande ERA5 | brut | colonne produite |
|---|---|---|
| temperature_2m_max | K | `tmax_c` (−273.15) |
| temperature_2m_min | K | `tmin_c` (−273.15) |
| dewpoint_temperature_2m | K | `dewp_c` (−273.15) |
| soil_temperature_level_1 | K | `soil_temp_c` (−273.15) |
| u_component_of_wind_10m | m/s | → `wind_speed_ms`, `wind_dir_deg` |
| v_component_of_wind_10m | m/s | → `wind_speed_ms`, `wind_dir_deg` |
| surface_pressure | Pa | `press_hpa` (÷100) |
| surface_solar_radiation_downwards_sum | J/m² | `ssr_mj_m2` (÷1e6) |
| volumetric_soil_water_layer_1 | m³/m³ | `soil_water` |

Features dérivées (mêmes formules que `Data-collector-pfe/clean_gsod_data.py`) :
`tmean_c`, `humidity_pct` (August-Roche-Magnus), `heat_index` (Rothfusz, **cible**), `wind_chill`.

> ⚠️ **`elevation`** : le `.tif` ne contient **pas** de bande d'altitude (MNT).
> L'altitude est donc **estimée** à partir de la pression de surface via la
> formule hypsométrique NOAA (`h = ((P0/P)^(1/5.257) − 1)·(T+273.15)/0.0065`,
> P0 = 1013.25 hPa), en prenant la **médiane annuelle** par pixel → valeur
> statique (0–2784 m, réaliste pour le Maroc). C'est un proxy, pas un MNT
> topographique. Pour une altitude exacte, ré-exporter depuis GEE en ajoutant
> une bande `USGS/SRTMGL1_003` (SRTM 30 m).

## « Est-ce que le LSTM prend des entrées `(batch_size, timesteps, features)` ? »

**Oui.** Un `keras.layers.LSTM` attend un tenseur 3D
`(batch_size, timesteps, n_features)`. Notre chaîne y arrive en 2 temps :

1. **Chaque point de grille = une « station ».** On déplie le cube
   `(153, 163, 364 jours, 9 vars)` en un tableau *long* :
   une ligne = `(pixel_id, latitude, longitude, date, features…)`.
   C'est le même format que `data/cleandata_gsod_by_station`, donc il se
   branche directement sur les notebooks LSTM existants.

2. **Fenêtres glissantes par pixel** (`make_sequences`) :
   `INPUT_WINDOW=7` jours d'entrée → `OUTPUT_WINDOW=7` jours à prédire.
   Résultat :
   - `X` de forme `(n_samples, 7, n_features)` ← entrée LSTM
   - `y` de forme `(n_samples, 7)` ← horizon

   ```python
   keras.layers.LSTM(128, input_shape=(INPUT_WINDOW, n_features))
   ```

> ⚠️ Les fenêtres sont construites **par `pixel_id`** et les lignes sont triées
> par `(pixel_id, date)` : aucune séquence ne franchit la frontière entre deux
> points de grille (pas de fuite temporelle).

## Utilisation

```bash
# génère le dataset long (parquet ~137 Mo) + un CSV d'aperçu
python3 era5_gridded/era5_to_lstm.py \
    --tif data2/ERA5_Morocco_2023.tif \
    --out data2/era5_morocco_2023_long.parquet \
    --csv-sample 20
```

Dans un notebook :

```python
import pandas as pd
from era5_gridded.era5_to_lstm import make_sequences

df = pd.read_parquet("data2/era5_morocco_2023_long.parquet")

FEATURES = ["latitude", "longitude", "elevation", "tmax_c", "dewp_c",
            "humidity_pct", "wind_speed_ms", "press_hpa", "ssr_mj_m2",
            "soil_water", "heat_index"]

X, y = make_sequences(df, FEATURES, target="heat_index",
                      input_window=7, output_window=7)
# X -> (n_samples, 7, 11)   y -> (n_samples, 7)
```

> ⚠️ **Normalisation** : comme pour GSOD, fit le scaler (MinMax / z-score)
> **uniquement sur le train** après le split chronologique, jamais sur tout le
> jeu, sous peine de fuite de données.

## Sortie (`data2/era5_morocco_2023_long.parquet`)

`2 311 400 lignes × 18 colonnes` (6350 pixels × 364 jours), 0 NaN.

| colonne | description |
|---|---|
| `pixel_id` | identifiant du point de grille (`row*W + col`) |
| `latitude`, `longitude` | centre du pixel (°) |
| `elevation` | altitude estimée depuis la pression (m, statique par pixel) |
| `date` | jour |
| `tmax_c`, `tmin_c`, `tmean_c`, `dewp_c` | températures (°C) |
| `humidity_pct` | humidité relative à `tmax_c` (%) |
| `wind_speed_ms`, `wind_dir_deg` | vent (m/s, ° convention météo) |
| `press_hpa` | pression de surface (hPa) |
| `ssr_mj_m2` | rayonnement solaire descendant (MJ/m²/jour) |
| `soil_temp_c`, `soil_water` | sol : température (°C), humidité (m³/m³) |
| `heat_index`, `wind_chill` | cibles ML (°C) |
