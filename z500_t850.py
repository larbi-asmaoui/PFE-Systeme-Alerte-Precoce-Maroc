import os
import time
import requests
import pandas as pd
import xarray as xr

# --- 1. Station List ---
STATIONS = [
    {"station": "Agadir Inezgane", "lat": 30.383, "lon": -9.567},
    {"station": "Agadir Al Massira", "lat": 30.319, "lon": -9.383},
    {"station": "Essaouira", "lat": 31.517, "lon": -9.783},
    {"station": "Marrakech Menara", "lat": 31.617, "lon": -8.032},
    {"station": "Ouarzazate", "lat": 30.933, "lon": -6.900},
    {"station": "Taroudant", "lat": 30.500, "lon": -8.817},
    {"station": "Tiznit", "lat": 29.683, "lon": -9.733},
    {"station": "Guelmim", "lat": 29.017, "lon": -10.050},
    {"station": "Tan-Tan", "lat": 28.450, "lon": -11.150},
    {"station": "Casablanca Anfa", "lat": 33.567, "lon": -7.667},
    {"station": "Nouasseur", "lat": 33.367, "lon": -7.583},
    {"station": "Rabat-Salé", "lat": 34.050, "lon": -6.767},
    {"station": "Kénitra", "lat": 34.300, "lon": -6.600},
    {"station": "Fès-Saïss", "lat": 33.933, "lon": -4.983},
    {"station": "Meknès", "lat": 33.883, "lon": -5.533},
    {"station": "Ifrane", "lat": 33.500, "lon": -5.167},
    {"station": "Midelt", "lat": 32.683, "lon": -4.733},
    {"station": "Errachidia", "lat": 31.967, "lon": -4.417},
    {"station": "Beni Mellal", "lat": 32.367, "lon": -6.400},
    {"station": "Khouribga", "lat": 32.867, "lon": -6.967},
    {"station": "Oujda Angads", "lat": 34.783, "lon": -1.933},
    {"station": "Nador Aroui", "lat": 34.983, "lon": -3.017},
    {"station": "Al Hoceima", "lat": 35.183, "lon": -3.850},
    {"station": "Tétouan Sania Ramel", "lat": 35.583, "lon": -5.333},
    {"station": "Tangier Boukhalef", "lat": 35.733, "lon": -5.900},
    {"station": "Larache", "lat": 35.183, "lon": -6.133},
    {"station": "Sidi Ifni", "lat": 29.367, "lon": -10.183},
    {"station": "Safi", "lat": 32.283, "lon": -9.233},
    {"station": "Dakhla", "lat": 23.700, "lon": -15.867},
    {"station": "Laâyoune", "lat": 27.933, "lon": -13.217}
]

# --- 2. Configuration ---
START_YEAR = 1990
END_YEAR = 1991
OUTPUT_DIR = "data/ml_ncep_upperair"
TMP_DIR = "data/ml_ncep_upperair/tmp"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TMP_DIR, exist_ok=True)

# We only want Geopotential Height (hgt) and Temperature (air)
VARIABLES = {
    'hgt': 'z',  # We'll rename it to z_500hPa later
    'air': 't'   # We'll rename it to t_850hPa later
}

# The pressure levels we care about
TARGET_LEVELS = [500.0, 850.0]

def download_file(url, local_path):
    """Downloads a file using requests with a progress indication."""
    if os.path.exists(local_path):
        return True
    
    print(f"    Downloading {os.path.basename(local_path)}...")
    try:
        response = requests.get(url, stream=True, timeout=120)
        response.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"    X Failed to download {url}: {e}")
        return False

def main():
    print("Starting NOAA NCEP Z500 & T850 Extraction...")
    
    for year in range(START_YEAR, END_YEAR + 1):
        print(f"\n--- Processing Year: {year} ---")
        
        downloaded_files = []
        
        # 1. Download only the 2 variable files for this year (hgt.nc and air.nc)
        success = True
        for var in VARIABLES.keys():
            url = f"https://downloads.psl.noaa.gov/Datasets/ncep.reanalysis.dailyavgs/pressure/{var}.{year}.nc"
            local_path = os.path.join(TMP_DIR, f"{var}_{year}.nc")
            
            if download_file(url, local_path):
                downloaded_files.append(local_path)
            else:
                success = False
                break
                
        if not success:
            print(f"  X Skipping year {year} due to download failure.")
            continue
            
        print("  -> Loading files into memory and extracting 30 stations...")
        
        try:
            # 2. Load the 2 datasets into xarray
            datasets = []
            for f in downloaded_files:
                ds = xr.open_dataset(f)
                ds = ds.sel(level=TARGET_LEVELS)
                datasets.append(ds)
                
            ds_year = xr.merge(datasets, compat='override')
            
            # 3. Extract data for each station
            for st in STATIONS:
                # NOAA uses 0 to 360 longitude
                lon_360 = (st['lon'] + 360) % 360
                
                # Extract nearest pixel
                station_ds = ds_year.sel(lat=st['lat'], lon=lon_360, method='nearest')
                df = station_ds.to_dataframe().reset_index()
                
                # Pivot table to get levels as columns
                df_pivot = df.pivot_table(
                    index='time',
                    columns='level',
                    values=list(VARIABLES.keys())
                )
                
                # Rename columns nicely based on the variable and level
                new_cols = []
                for var, level in df_pivot.columns:
                    nice_name = VARIABLES[var]
                    new_cols.append(f"{nice_name}_{int(level)}hPa")
                
                df_pivot.columns = new_cols
                df_pivot = df_pivot.reset_index()
                df_pivot['date'] = df_pivot['time'].dt.date
                
                # IMPORTANT: Keep ONLY z_500hPa and t_850hPa (Drop z_850 and t_500)
                cols_to_keep = ['date', 'z_500hPa', 't_850hPa']
                # Check if columns exist (safety check)
                cols_present = [c for c in cols_to_keep if c in df_pivot.columns]
                df_final = df_pivot[cols_present].copy()
                
                # Convert T850 from Kelvin to Celsius
                if 't_850hPa' in df_final.columns:
                    df_final['t_850hPa'] = df_final['t_850hPa'] - 273.15
                
                # 4. Save to CSV immediately! (Append if year > START_YEAR)
                out_path = os.path.join(OUTPUT_DIR, f"{st['station'].replace(' ', '_')}_upperair.csv")
                
                if not os.path.exists(out_path):
                    df_final.to_csv(out_path, index=False)
                else:
                    df_final.to_csv(out_path, mode='a', header=False, index=False)
            
            print(f"  ✓ Z500 & T850 extracted for {year}.")
            
        except Exception as e:
            print(f"  X Error processing data for {year}: {e}")
            
        finally:
            # 5. Close datasets and delete the downloaded .nc files to save space
            try:
                for ds in datasets:
                    ds.close()
            except:
                pass
                
            print("  -> Cleaning up temporary files...")
            for f in downloaded_files:
                if os.path.exists(f):
                    os.remove(f)

    print("\nZ500 and T850 Data Collection Complete!")

if __name__ == "__main__":
    main()