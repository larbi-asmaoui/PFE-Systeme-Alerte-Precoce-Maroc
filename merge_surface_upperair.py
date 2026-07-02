import os
import pandas as pd

# --- 1. Configuration ---
SURFACE_DIR = "data/nasa_power_stations_csv"
UPPERAIR_DIR = "data/ml_ncep_upperair"
OUTPUT_DIR = "data/ml_final_merged_csv"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- 2. Station List (List of Dictionaries) ---
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

def main():
    print(f"Starting Data Merge for {len(STATIONS)} stations...\n")
    
    successful_merges = 0
    
    for st in STATIONS:
        # Extract the station name from the dictionary
        station_name = st["station"]
        
        # Format filename (replacing spaces and hyphens with underscores)
        safe_name = station_name.replace(' ', '_').replace('-', '_')
        
        surface_file = os.path.join(SURFACE_DIR, f"{safe_name}.csv")
        upperair_file = os.path.join(UPPERAIR_DIR, f"{safe_name}_upperair.csv")
        output_file = os.path.join(OUTPUT_DIR, f"{safe_name}.csv")
        
        # Check if both files exist
        if not os.path.exists(surface_file):
            print(f"  X Missing Surface data for {station_name}. Skipping.")
            continue
        if not os.path.exists(upperair_file):
            print(f"  X Missing Upper-Air data for {station_name}. Skipping.")
            continue
            
        try:
            # 1. Load both CSVs
            df_surface = pd.read_csv(surface_file)
            df_upperair = pd.read_csv(upperair_file)
            
            # Ensure 'date' columns are formatted exactly the same (as strings)
            df_surface['date'] = pd.to_datetime(df_surface['date']).dt.strftime('%Y-%m-%d')
            df_upperair['date'] = pd.to_datetime(df_upperair['date']).dt.strftime('%Y-%m-%d')
            
            # 2. Merge on the 'date' column
            # 'inner' means we only keep days where BOTH surface and upper-air exist
            df_merged = pd.merge(df_surface, df_upperair, on='date', how='inner')
            
            # 3. Clean up any remaining NaNs just in case
            df_merged = df_merged.ffill().bfill()
            
            # 4. Save the Final CSV
            df_merged.to_csv(output_file, index=False)
            
            print(f"  ✓ Merged {station_name}: {len(df_merged)} rows saved -> {output_file}")
            successful_merges += 1
            
        except Exception as e:
            print(f"  X Error merging data for {station_name}: {e}")

    print(f"\nMerge Complete! {successful_merges}/{len(STATIONS)} stations are ready for LSTM training.")

if __name__ == "__main__":
    main()