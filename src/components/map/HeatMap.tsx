"use client";

import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { Box, Typography, Grid } from "@mui/material";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface RegionData {
  id: number;
  name: string;
  coords: [number, number];
  alert: string;
  temp: number;
  tmin?: number;
  rh?: number;
  heat_index?: number;
  severity?: number;
  date?: string;
}

interface HeatMapProps {
  regions: RegionData[];
}

const alertColors: Record<string, string> = {
  red: "#d32f2f",
  orange: "#ed6c02",
  yellow: "#ffeb3b",
  none: "#e0e0e0",
};

const alertLabels: Record<string, string> = {
  red: "Extrême",
  orange: "Sévère",
  yellow: "Modérée",
  none: "Aucune",
};

const getRadius = (alert: string): number => {
  if (alert === "red") return 25;
  if (alert === "orange") return 18;
  return 12;
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function HeatMap({ regions }: HeatMapProps) {
  return (
    <Box
      sx={{
        height: "100%",
        width: "100%",
        position: "absolute",
        top: 0,
        left: 0,
        zIndex: 0,
      }}
    >
      <MapContainer
        {...{
          center: [31.7917, -7.0926] as [number, number],
          zoom: 6,
          zoomControl: false,
          style: { height: "100%", width: "100%" },
        }}
      >
        <TileLayer
          {...{
            url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
            attribution:
              '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
          }}
        />

        {regions.map((region) => (
          <CircleMarker
            key={region.id}
            {...{
              center: region.coords,
              radius: getRadius(region.alert),
            }}
            pathOptions={{
              color: alertColors[region.alert],
              fillColor: alertColors[region.alert],
              fillOpacity: 0.6,
              weight: 2,
            }}
          >
            <Popup>
              <Box sx={{ minWidth: 160 }}>
                <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
                  {region.name}
                </Typography>
                <Typography
                  variant="body2"
                  sx={{
                    color: alertColors[region.alert],
                    fontWeight: 600,
                    mb: 0.5,
                  }}
                >
                  {alertLabels[region.alert]} — {region.temp.toFixed(1)}°C
                </Typography>

                <Grid container spacing={0.5}>
                  <Grid size={6}>
                    <Typography variant="caption" color="text.secondary">
                      T<sub>max</sub>
                    </Typography>
                    <Typography variant="body2" fontWeight={600}>
                      {region.temp.toFixed(1)}°C
                    </Typography>
                  </Grid>
                  <Grid size={6}>
                    <Typography variant="caption" color="text.secondary">
                      T<sub>min</sub>
                    </Typography>
                    <Typography variant="body2" fontWeight={600}>
                      {region.tmin?.toFixed(1) ?? "—"}°C
                    </Typography>
                  </Grid>
                  <Grid size={6}>
                    <Typography variant="caption" color="text.secondary">
                      Heat Index
                    </Typography>
                    <Typography variant="body2" fontWeight={600}>
                      {region.heat_index?.toFixed(1) ?? "—"}°C
                    </Typography>
                  </Grid>
                  <Grid size={6}>
                    <Typography variant="caption" color="text.secondary">
                      Humidité
                    </Typography>
                    <Typography variant="body2" fontWeight={600}>
                      {region.rh?.toFixed(0) ?? "—"}%
                    </Typography>
                  </Grid>
                </Grid>

                {region.date && (
                  <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
                    {region.date}
                  </Typography>
                )}
              </Box>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </Box>
  );
}
