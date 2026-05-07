import xarray as xr
import os
from pathlib import Path

# Paths to your files
INPUT_NC = "backend/artifacts/seuils_climatologiques_mensuels.nc" 
OUTPUT_NC = "backend/artifacts/seuils_climatologiques_globaux.nc"

def calculate_global_percentiles():
    if not os.path.exists(INPUT_NC):
        print(f"Error: Could not find {INPUT_NC}")
        return

    print(f"Loading raw daily dataset from {INPUT_NC}...")
    ds = xr.open_dataset(INPUT_NC, engine="netcdf4")

    # We match the 37x65 domain required by the model [36, -17, 27, -1]
    ds = ds.sel(latitude=slice(36, 27), longitude=slice(-17, -1))
    
    print("Calculating global 90th percentile for tmax per pixel (across all time/months)...")
    # Using skipna in case of any missing values
    tmax_90p = ds["tmax"].quantile(0.9, dim="time", skipna=True).drop_vars("quantile", errors="ignore")
    tmax_90p.name = "tmax_90p"
    
    print("Calculating global 10th percentile for tmin per pixel (across all time/months)...")
    tmin_10p = ds["tmin"].quantile(0.1, dim="time", skipna=True).drop_vars("quantile", errors="ignore")
    tmin_10p.name = "tmin_10p"

    print("Merging into new dataset...")
    # Create a new dataset containing only our 2D percentiles maps
    out_ds = xr.Dataset({
        "tmax_90p": tmax_90p,
        "tmin_10p": tmin_10p
    })
    
    # Save the file
    print(f"Saving to {OUTPUT_NC}...")
    out_ds.to_netcdf(OUTPUT_NC, engine="netcdf4")
    
    ds.close()
    out_ds.close()
    print("Successfully generated global percentiles!")

if __name__ == "__main__":
    calculate_global_percentiles()
