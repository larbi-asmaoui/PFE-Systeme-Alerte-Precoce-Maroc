import os
import time
import requests
import xarray as xr
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- 1. Configuration ---
START_YEAR = 2020
END_YEAR = 2026
OUTPUT_DIR = "data/nasa_power_grid"
TMP_DIR = os.path.join(OUTPUT_DIR, "tmp")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TMP_DIR, exist_ok=True)

# NASA POWER Variables
PARAMETERS = [
    "T2M_MAX", "T2M_MIN", "T2M", "RH2M", 
    "WS10M", "WD10M", "PS", "PRECTOTCORR", "ALLSKY_SFC_SW_DWN"
]

# Full Morocco Bounding Box: Lat 21 to 36, Lon -17 to -1 (4 chunks to bypass NASA limits)
BBOXES = {
    "NorthWest": {"lat_min": 28.5, "lat_max": 36.0, "lon_min": -17.0, "lon_max": -9.0},
    "NorthEast": {"lat_min": 28.5, "lat_max": 36.0, "lon_min": -9.0,  "lon_max": -1.0},
    "SouthWest": {"lat_min": 21.0, "lat_max": 28.5, "lon_min": -17.0, "lon_max": -9.0},
    "SouthEast": {"lat_min": 21.0, "lat_max": 28.5, "lon_min": -9.0,  "lon_max": -1.0}
}

# --- 2. Feature Engineering Formulas ---
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

# --- 3. Downloading & Merging ---
def download_single_parameter(year, region_name, coords, param):
    """Downloads one parameter for one region and year."""
    start_date = f"{year}0101"
    
    if year == datetime.now().year:
        end_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
    else:
        end_date = f"{year}1231"
        
    url = (
        f"https://power.larc.nasa.gov/api/temporal/daily/regional?"
        f"parameters={param}&community=RE"
        f"&latitude-min={coords['lat_min']}&latitude-max={coords['lat_max']}"
        f"&longitude-min={coords['lon_min']}&longitude-max={coords['lon_max']}"
        f"&start={start_date}&end={end_date}&format=NETCDF"
    )
    
    file_path = os.path.join(TMP_DIR, f"morocco_{region_name}_{year}_{param}.nc")
    
    if os.path.exists(file_path):
        return file_path 

    print(f"    -> Requesting {param}...")
    for attempt in range(1, 4):
        try:
            response = requests.get(url, stream=True, timeout=300)
            if response.status_code == 200:
                with open(file_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                return file_path
            elif response.status_code == 429:
                print(f"       X Rate limit. Retrying in 30s...")
                time.sleep(30)
            else:
                print(f"       X Error {response.status_code}: {response.text}")
                break
        except Exception as e:
            print(f"       X Attempt {attempt}/3 failed: {str(e)}")
            time.sleep(10)
            
    return None

def merge_parameters(year, region_name, param_files):
    """Converts NetCDF chunks to DataFrames, engineers features, and saves to Parquet."""
    final_path = os.path.join(OUTPUT_DIR, f"morocco_{region_name}_{year}.parquet")
    
    if os.path.exists(final_path):
        print(f"  ✓ Final merged file already exists: {final_path}")
        return
        
    print(f"  -> Merging and computing features for {len(param_files)} parameters...")
    try:
        master_df = None
        
        for f in param_files:
            ds = xr.open_dataset(f)
            df = ds.to_dataframe().reset_index()
            ds.close()
            
            cols_to_keep = ['time', 'lat', 'lon'] + [c for c in df.columns if c in PARAMETERS]
            df = df[cols_to_keep]
            
            df['lat'] = df['lat'].round(2)
            df['lon'] = df['lon'].round(2)
            
            if master_df is None:
                master_df = df
            else:
                master_df = pd.merge(master_df, df, on=['time', 'lat', 'lon'], how='outer')

        # Drop rows where everything is NaN (ocean edges in NASA data)
        master_df = master_df.dropna(subset=PARAMETERS, how='all')

        # --- APPLY FEATURE ENGINEERING ---
        if not master_df.empty:
            # Vectorize Wind
            wdir_rad = np.radians(master_df['WD10M'])
            master_df['u_wind'] = -master_df['WS10M'] * np.sin(wdir_rad)
            master_df['v_wind'] = -master_df['WS10M'] * np.cos(wdir_rad)
            
            # Unit Conversions
            master_df['Press_hPa'] = master_df['PS'] * 10  # kPa to hPa
            master_df['Solar_Jm2'] = master_df['ALLSKY_SFC_SW_DWN'] * 3600000  # kW-hr/m2 to J/m2
            
            # Targets
            master_df['HeatIndex'] = calculate_heat_index(master_df['T2M_MAX'], master_df['RH2M'])
            master_df['WindChill'] = calculate_wind_chill(master_df['T2M_MIN'], master_df['WS10M'])
            
            # Clean up missing data (forward fill)
            master_df.ffill(inplace=True)

        # Save to Parquet
        master_df.to_parquet(final_path, index=False)
        print(f"  ✓ Saved ML-ready Parquet table: {final_path}")
        
        # Clean up temporary chunks
        for f in param_files:
            os.remove(f)
            
    except Exception as e:
        print(f"  X Failed to merge files: {e}")

def main():
    print("Starting NASA POWER Distributed Grid Download (Full Morocco)...")
    
    for year in range(START_YEAR, END_YEAR + 1):
        print(f"\n=== Year: {year} ===")
        for region_name, coords in BBOXES.items():
            print(f" Region: {region_name}")
            
            final_path = os.path.join(OUTPUT_DIR, f"morocco_{region_name}_{year}.parquet")
            if os.path.exists(final_path):
                print(f"  ✓ Already completed. Skipping.")
                continue

            downloaded_files = []
            for param in PARAMETERS:
                filepath = download_single_parameter(year, region_name, coords, param)
                if filepath:
                    downloaded_files.append(filepath)
                time.sleep(3)
                
            if len(downloaded_files) == len(PARAMETERS):
                merge_parameters(year, region_name, downloaded_files)
            else:
                print(f"  X Missing some parameters. Skipping merge for {region_name} {year}.")

if __name__ == "__main__":
    main()