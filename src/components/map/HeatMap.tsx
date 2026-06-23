"use client";

import { useMemo } from "react";
import { MapContainer, TileLayer, GeoJSON, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { Box } from "@mui/material";
import L from "leaflet";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface ForecastDay {
  day: number;
  date: string;
  tmax: number;
  tmin: number;
  rh: number;
  heat_index: number;
  severity: number;
  alert_level: string;
}

export interface GridCellProperties {
  row: number;
  col: number;
  lat: number;
  lon: number;
  alert_level: string;
  severity: number;
  forecasts: ForecastDay[];
}

export interface GeoJSONFeature {
  type: "Feature";
  geometry: {
    type: "Polygon";
    coordinates: number[][][];
  };
  properties: GridCellProperties;
}

export interface GeoJSONData {
  type: "FeatureCollection";
  features: GeoJSONFeature[];
}

interface HeatMapProps {
  geojson: GeoJSONData | null;
  selectedDay: number;
  onCellClick?: (lat: number, lon: number) => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const alertColors: Record<string, string> = {
  red: "#d32f2f",
  orange: "#ed6c02",
  yellow: "#ffeb3b",
  none: "#e0e0e0",
};

const alertFillOpacity: Record<string, number> = {
  red: 0.65,
  orange: 0.55,
  yellow: 0.45,
  none: 0.2,
};

const alertLabels: Record<string, string> = {
  red: "Extrême",
  orange: "Sévère",
  yellow: "Modérée",
  none: "Aucune",
};

// ---------------------------------------------------------------------------
// Fit map to bounds once data loads
// ---------------------------------------------------------------------------
function FitBounds({ geojson }: { geojson: GeoJSONData | null }) {
  const map = useMap();
  useMemo(() => {
    if (geojson && geojson.features.length > 0) {
      const layer = L.geoJSON(geojson as GeoJSONData);
      map.fitBounds(layer.getBounds().pad(0.05));
    }
  }, [geojson, map]);
  return null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function HeatMap({ geojson, selectedDay, onCellClick }: HeatMapProps) {
  const geoJSONKey = useMemo(() => `day-${selectedDay}`, [selectedDay]);

  const onEachFeature = useMemo(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    () => (feature: any, layer: L.Layer) => {
      const props = feature.properties as GridCellProperties;
      const forecast = props.forecasts[selectedDay] || props.forecasts[0];
      if (!forecast) return;

      const color = alertColors[forecast.alert_level] || alertColors.none;
      const label = alertLabels[forecast.alert_level] || alertLabels.none;

      const popupHtml = `
        <div style="min-width:180px;font-family:system-ui,sans-serif;">
          <div style="font-weight:600;font-size:14px;margin-bottom:4px;">
            ${props.lat.toFixed(2)}°N, ${props.lon.toFixed(2)}°E
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 12px;font-size:13px;">
            <span style="color:#666;">T<sub>max</sub></span>
            <span style="font-weight:600;">${forecast.tmax.toFixed(1)}°C</span>
            <span style="color:#666;">T<sub>min</sub></span>
            <span style="font-weight:600;">${forecast.tmin.toFixed(1)}°C</span>
            <span style="color:#666;">Heat Index</span>
            <span style="font-weight:600;color:${color};">${forecast.heat_index.toFixed(1)}°C</span>
            <span style="color:#666;">Humidité</span>
            <span style="font-weight:600;">${forecast.rh.toFixed(0)}%</span>
          </div>
          <div style="margin-top:6px;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600;background:${color};color:${forecast.alert_level === "yellow" ? "#333" : "#fff"};">
            ${label}
          </div>
          <div style="margin-top:4px;font-size:11px;color:#999;">
            ${forecast.date} | J+${forecast.day}
          </div>
        </div>
      `;

      layer.bindPopup(popupHtml);

      if (onCellClick) {
        layer.on("click", () => {
          onCellClick(props.lat, props.lon);
        });
      }
    },
    [selectedDay, onCellClick],
  );

  const geoStyle = useMemo(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    () => (feature: any) => {
      const props = feature.properties as GridCellProperties;
      const forecast = props.forecasts[selectedDay] || props.forecasts[0];
      const level = forecast?.alert_level || "none";

      return {
        fillColor: alertColors[level],
        fillOpacity: alertFillOpacity[level],
        color: "#ffffff",
        weight: 0.5,
        opacity: 0.4,
      };
    },
    [selectedDay],
  );

  return (
    <Box
      {...{
        sx: {
          height: "100%",
          width: "100%",
          position: "absolute",
          top: 0,
          left: 0,
          zIndex: 0,
        },
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

        {geojson && (
          <GeoJSON
            {...{
              key: geoJSONKey,
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              data: geojson as any,
              style: geoStyle,
              onEachFeature: onEachFeature,
            }}
          />
        )}

        <FitBounds geojson={geojson} />
      </MapContainer>
    </Box>
  );
}
