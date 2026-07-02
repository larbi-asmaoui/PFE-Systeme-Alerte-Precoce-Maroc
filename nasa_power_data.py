import os
import time
import requests
import pandas as pd
import numpy as np
import math

# --- 1. Station List ---
STATIONS = [
    {"station": "Agadir Inezgane", "city": "Agadir", "lat": 30.383, "lon": -9.567},
    {"station": "Agadir Al Massira", "city": "Agadir", "lat": 30.319, "lon": -9.383},
    {"station": "Essaouira", "city": "Essaouira", "lat": 31.517, "lon": -9.783},
    {"station": "Marrakech Menara", "city": "Marrakech", "lat": 31.617, "lon": -8.032},
    {"station": "Ouarzazate", "city": "Ouarzazate", "lat": 30.933, "lon": -6.900},
    {"station": "Taroudant", "city": "Taroudant", "lat": 30.500, "lon": -8.817},
    {"station": "Tiznit", "city": "Tiznit", "lat": 29.683, "lon": -9.733},
    {"station": "Guelmim", "city": "Guelmim", "lat": 29.017, "lon": -10.050},
    {"station": "Tan-Tan", "city": "Tan-Tan", "lat": 28.450, "lon": -11.150},
    {"station": "Casablanca Anfa", "city": "Casablanca", "lat": 33.567, "lon": -7.667},
    {"station": "Nouasseur", "city": "Casablanca", "lat": 33.367, "lon": -7.583},
    {"station": "Rabat-Salé", "city": "Rabat", "lat": 34.050, "lon": -6.767},
    {"station": "Kénitra", "city": "Kénitra", "lat": 34.300, "lon": -6.600},
    {"station": "Fès-Saïss", "city": "Fès", "lat": 33.933, "lon": -4.983},
    {"station": "Meknès", "city": "Meknès", "lat": 33.883, "lon": -5.533},
    {"station": "Ifrane", "city": "Ifrane", "lat": 33.500, "lon": -5.167},
    {"station": "Midelt", "city": "Midelt", "lat": 32.683, "lon": -4.733},
    {"station": "Errachidia", "city": "Errachidia", "lat": 31.967, "lon": -4.417},
    {"station": "Beni Mellal", "city": "Beni Mellal", "lat": 32.367, "lon": -6.400},
    {"station": "Khouribga", "city": "Khouribga", "lat": 32.867, "lon": -6.967},
    {"station": "Oujda Angads", "city": "Oujda", "lat": 34.783, "lon": -1.933},
    {"station": "Nador Aroui", "city": "Nador", "lat": 34.983, "lon": -3.017},
    {"station": "Al Hoceima", "city": "Al Hoceima", "lat": 35.183, "lon": -3.850},
    {"station": "Tétouan Sania Ramel", "city": "Tétouan", "lat": 35.583, "lon": -5.333},
    {"station": "Tangier Boukhalef", "city": "Tangier", "lat": 35.733, "lon": -5.900},
    {"station": "Larache", "city": "Larache", "lat": 35.183, "lon": -6.133},
    {"station": "Sidi Ifni", "city": "Sidi Ifni", "lat": 29.367, "lon": -10.183},
    {"station": "Safi", "city": "Safi", "lat": 32.283, "lon": -9.233},
    {"station": "Dakhla", "city": "Dakhla", "lat": 23.700, "lon": -15.867},
    {"station": "Laâyoune", "city": "Laâyoune", "lat": 27.933, "lon": -13.217}
]

# --- 2. Moroccan Coastline Points ---
COASTLINE_POINTS = [
    (35.08, -2.23), (35.25, -3.93), (35.78, -5.81), (34.26, -6.66), (34.02, -6.84),
    (33.60, -7.63), (33.25, -8.50), (32.30, -9.23), (31.51, -9.77), (30.42, -9.59),
    (29.38, -10.17), (28.49, -11.32), (27.93, -12.92), (27.09, -13.41), (26.12, -14.48),
    (23.71, -15.93), (21.32, -16.96)
]

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

def distance_to_ocean(lat, lon):
    return min(haversine_distance(lat, lon, clat, clon) for clat, clon in COASTLINE_POINTS)

# --- 3. Feature Engineering ---
def calculate_heat_index(tmax_c, rh):
    tf = tmax_c * 1.8 + 32.0
    hi_simple = 0.5 * (tf + 61.0 + ((tf - 68.0) * 1.2) + (rh * 0.094))
    hi_full = (-42.379 + 2.04901523 * tf + 10.14333127 * rh - 0.22475541 * tf * rh 
               - 0.00683783 * tf**2 - 0.05481717 * rh**2 + 0.00122874 * tf**2 * rh 
               + 0.00085282 * tf * rh**2 - 0.00000199 * tf**2 * rh**2)
    hi_f = np.where(tf >= 80, hi_full, hi_simple)
    return (hi_f - 32.0) / 1.8

def calculate_wind_chill(tmin_c, wind_speed_ms):
    v_mph = wind_speed_ms * 2.23694
    tf_min = tmin_c * 1.8 + 32.0
    wc_f = 35.74 + 0.6215 * tf_min - 35.75 * (v_mph**0.16) + 0.4275 * tf_min * (v_mph**0.16)
    wc_f = np.where(v_mph > 3.0, wc_f, tf_min)
    return (wc_f - 32.0) / 1.8

# --- 4. Main Script ---
# NASA POWER expects dates in YYYYMMDD format
START_DATE = "19900101"
END_DATE = "20251231"
OUTPUT_DIR = "data/nasa_power_stations_csv"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def fetch_nasa_power(lat, lon):
    """Fetches data from NASA POWER API."""
    # NASA POWER Parameters: 
    # T2M_MAX (Max Temp), T2M_MIN (Min Temp), T2M (Mean Temp), RH2M (Relative Humidity)
    # WS10M (Wind Speed), WD10M (Wind Direction), PS (Pressure in kPa)
    # PRECTOTCORR (Precipitation mm/day), ALLSKY_SFC_SW_DWN (Solar Radiation kW-hr/m^2/day)
    
    url = (
        f"https://power.larc.nasa.gov/api/temporal/daily/point?"
        f"parameters=T2M_MAX,T2M_MIN,T2M,RH2M,WS10M,WD10M,PS,PRECTOTCORR,ALLSKY_SFC_SW_DWN"
        f"&community=RE&longitude={lon}&latitude={lat}&start={START_DATE}&end={END_DATE}&format=JSON"
    )
    
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.json()

def main():
    print(f"Starting NASA POWER data collection for {len(STATIONS)} Moroccan stations...\n")
    
    for i, st in enumerate(STATIONS):
        print(f"[{i+1}/{len(STATIONS)}] Downloading {st['station']} via NASA POWER...")
        dist_ocean = distance_to_ocean(st["lat"], st["lon"])
        
        try:
            data = fetch_nasa_power(st["lat"], st["lon"])
            
            # Extract elevation from metadata
            elevation = data['geometry']['coordinates'][2]
            
            # Extract time series parameters
            df = pd.DataFrame(data['properties']['parameter'])
            df.index = pd.to_datetime(df.index, format='%Y%m%d')
            df = df.reset_index().rename(columns={'index': 'date'})
            
            # NASA POWER uses -999.0 for missing data. Replace with NaN and interpolate.
            df = df.replace(-999.0, np.nan)
            df = df.interpolate(method='linear').ffill().bfill()
            
            # --- Unit Conversions to match ERA5-Land ---
            # Pressure: NASA is kPa -> Multiply by 10 for hPa
            df['Press_hPa'] = df['PS'] * 10 
            
            # Solar: NASA is kW-hr/m^2/day -> Multiply by 3,600,000 for J/m^2
            df['Solar_Jm2'] = df['ALLSKY_SFC_SW_DWN'] * 3600000 
            
            # Wind: NASA speed is m/s already.
            wdir_rad = np.radians(df['WD10M'])
            df['u_wind'] = -df['WS10M'] * np.sin(wdir_rad)
            df['v_wind'] = -df['WS10M'] * np.cos(wdir_rad)
            
            # Create Final Output DataFrame
            df_final = pd.DataFrame({
                "date": df['date'].dt.date,
                "Tmax": df['T2M_MAX'],
                "Tmin": df['T2M_MIN'],
                "Tmean": df['T2M'],
                "RH": df['RH2M'],
                "WindSpeed_ms": df['WS10M'],
                "u_wind": df['u_wind'],
                "v_wind": df['v_wind'],
                "Press_hPa": df['Press_hPa'],
                "Solar_Jm2": df['Solar_Jm2'],
                "Precipitation_mm": df['PRECTOTCORR']
            })
            
            # Add Targets & Static Features
            df_final['HeatIndex'] = calculate_heat_index(df_final['Tmax'], df_final['RH'])
            df_final['WindChill'] = calculate_wind_chill(df_final['Tmin'], df_final['WindSpeed_ms'])
            
            df_final['latitude'] = st["lat"]
            df_final['longitude'] = st["lon"]
            df_final['elevation_m'] = elevation
            df_final['distance_to_ocean_km'] = round(dist_ocean, 2)

            # Save to CSV
            filename = f"{st['station'].replace(' ', '_').replace('-', '_')}.csv"
            filepath = os.path.join(OUTPUT_DIR, filename)
            df_final.to_csv(filepath, index=False)
            
            print(f"  ✓ Saved {len(df_final)} daily records to {filename}")
            
            # Short sleep out of courtesy to NASA servers
            time.sleep(1)
            
        except Exception as e:
            print(f"  X Error downloading {st['station']}: {str(e)}")

if __name__ == "__main__":
    main()