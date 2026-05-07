import sys
import numpy as np

with open('/home/asmaoui/Documents/GitHub/PFE-Systeme-Alerte-Precoce-Maroc/backend/predictor.py', 'r') as f:
    code = f.read()

OLD = """    # If maximum severity across any day is > 0, emit it
    max_severity = np.max(severity_matrix, axis=0) if severity_matrix.ndim == 3 else severity_matrix
    rows, cols = np.where(max_severity > 0)

    for r, c in zip(rows, cols):
        sev_val = float(max_severity[r, c])
        
        features.append({
            "type": "Feature",
            "geometry": {
                "type":        "Point",
                "coordinates": [float(lon_grid[r, c]), float(lat_grid[r, c])],
            },
            "properties": {
                "region_lat":    float(latitudes[r]),
                "region_lon":    float(longitudes[c]),
                "alert_level":   _severity_to_alert_level(sev_val),
                "predicted_temp": float(round(pred_tmax[0, r, c], 1)),
                "severity":      float(round(sev_val, 1)),
                "threshold":     "tmax_90p",
                "forecast_tmax": [round(float(x), 1) for x in pred_tmax[:, r, c]],
                "forecast_tmin": [round(float(x), 1) for x in pred_tmin[:, r, c]],
                "forecast_rh":   [round(float(x), 1) for x in pred_rh[:, r, c]],
                "forecast_hi":   [round(float(x), 1) for x in pred_hi[:, r, c]],
            },
        })"""

NEW = """    # Moroccan Cities definition
    MOROCCO_CITIES = [
        {"name": "Casablanca", "lat": 33.5731, "lon": -7.5898},
        {"name": "Rabat", "lat": 34.0209, "lon": -6.8416},
        {"name": "Marrakech", "lat": 31.6295, "lon": -7.9811},
        {"name": "Agadir", "lat": 30.4278, "lon": -9.5981},
        {"name": "Fès", "lat": 34.0331, "lon": -5.0003},
        {"name": "Tangier", "lat": 35.7595, "lon": -5.8340},
        {"name": "Meknès", "lat": 33.8920, "lon": -5.5510},
        {"name": "Oujda", "lat": 34.6814, "lon": -1.9086},
        {"name": "Kenitra", "lat": 34.2610, "lon": -6.5802},
        {"name": "Tetouan", "lat": 35.5889, "lon": -5.3626},
        {"name": "Safi", "lat": 32.2994, "lon": -9.2372},
        {"name": "Mohammedia", "lat": 33.3093, "lon": -8.4552},
        {"name": "Beni Mellal", "lat": 32.3373, "lon": -6.3498},
        {"name": "Nador", "lat": 35.1667, "lon": -2.9333},
        {"name": "Taza", "lat": 34.2155, "lon": -4.0120},
        {"name": "Settat", "lat": 33.0010, "lon": -7.6166},
        {"name": "Khouribga", "lat": 32.8811, "lon": -6.9063},
        {"name": "Errachidia", "lat": 31.9314, "lon": -4.4244},
        {"name": "Dakhla", "lat": 28.9866, "lon": -10.0573},
        {"name": "Guelmim", "lat": 28.9869, "lon": -10.0573},
        {"name": "Al Hoceima", "lat": 35.2442, "lon": -3.9317},
        {"name": "Essaouira", "lat": 31.5125, "lon": -9.7700}
    ]

    max_severity = np.max(severity_matrix, axis=0) if severity_matrix.ndim == 3 else severity_matrix

    # Map each city to nearest grid point
    # latitudes is [36..27] decreasing
    # longitudes is [-17..-1] increasing
    added_cities = set()
    for city in MOROCCO_CITIES:
        # Find nearest lat
        r = np.abs(latitudes - city["lat"]).argmin()
        c = np.abs(longitudes - city["lon"]).argmin()
        sev_val = float(max_severity[r, c])
        
        # We output all tracking cities or just > 0? Let's output all cities so we can see forecast, but maybe severity handles color.
        # Actually user wants to click and see forecast, if we only output > 0, normal cities won't appear.
        # Let's map all these major cities regardless of severity, or maybe only if sev_val > 0.
        # Let's output all of them, the UI will color by alert_level (yellow if none, or green).
        features.append({
            "type": "Feature",
            "geometry": {
                "type":        "Point",
                "coordinates": [float(city["lon"]), float(city["lat"])],
            },
            "properties": {
                "name":          city["name"],
                "region_lat":    float(city["lat"]),
                "region_lon":    float(city["lon"]),
                "alert_level":   _severity_to_alert_level(sev_val),
                "predicted_temp": float(round(pred_tmax[0, r, c], 1)),
                "severity":      float(round(sev_val, 1)),
                "threshold":     "tmax_90p",
                "forecast_tmax": [round(float(x), 1) for x in pred_tmax[:, r, c]],
                "forecast_tmin": [round(float(x), 1) for x in pred_tmin[:, r, c]],
                "forecast_rh":   [round(float(x), 1) for x in pred_rh[:, r, c]],
                "forecast_hi":   [round(float(x), 1) for x in pred_hi[:, r, c]],
            },
        })"""

code = code.replace(OLD, NEW)
with open('/home/asmaoui/Documents/GitHub/PFE-Systeme-Alerte-Precoce-Maroc/backend/predictor.py', 'w') as f:
    f.write(code)

print("Cities generated successfully")
