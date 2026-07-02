"use client";

import { useMemo } from "react";
import DeckGL from "@deck.gl/react";
import { GeoJsonLayer } from "@deck.gl/layers";
import type { PickingInfo } from "@deck.gl/core";
import type { Feature, Geometry } from "geojson";
import { Map } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import { Box } from "@mui/material";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface ForecastDay {
  day: number;
  date: string;
  heat_index: number;
  wind_chill: number;
  severity: number;
  alert_level: string;
}

export interface GridCellProperties {
  // legacy grid (kept optional for back-compat); Sedona hexes carry `h3` instead.
  row?: number;
  col?: number;
  h3?: string;
  lat: number;
  lon: number;
  alert_level: string;
  severity: number;
  // Compact per-day arrays as written by Stage 2 (small files); the dashboard
  // expands them into `forecasts` on load. `dates` live at the collection level.
  hi?: number[];
  wc?: number[];
  sev?: number[];
  lvl?: string[];
  forecasts: ForecastDay[];
}

export interface GeoJSONFeature {
  type: "Feature";
  geometry: {
    type: "Polygon" | "Point";
    coordinates: number[][][] | number[];
  };
  properties: GridCellProperties;
}

export interface GeoJSONData {
  type: "FeatureCollection";
  dates?: string[];
  features: GeoJSONFeature[];
}

export type MapMetric = "heat" | "cold";

interface HeatMapProps {
  geojson: GeoJSONData | null;
  selectedDay: number;
  metric: MapMetric;
  onCellClick?: (lat: number, lon: number) => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
// Open / free MapLibre vector style (no API key) — light Carto "Positron".
const MAP_STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

const INITIAL_VIEW_STATE = {
  longitude: -7.0926,
  latitude: 31.7917,
  zoom: 5,
  pitch: 0, // 2D top-down view (no tilt)
  bearing: 0,
};

type RGB = [number, number, number];

// Heat Index colour ramp (°C), anchored to the US NWS classification thresholds
// (<27 Low risk, 27–32 Caution, 33–39 Extreme Caution, 40–51 Danger, >51 Extreme
// Danger) and shaded like the NOAA/WPC heat-index field (green → yellow → orange
// → red → dark purple).
const HEAT_STOPS: Array<[number, RGB]> = [
  [18, [199, 233, 180]], //  low risk — light green
  [27, [255, 255, 178]], //  caution — pale yellow
  [33, [254, 204, 92]], //   extreme caution — amber
  [40, [253, 141, 60]], //   danger — orange
  [46, [240, 59, 32]], //    danger — red
  [51, [189, 0, 38]], //     extreme danger — deep red
  [57, [94, 11, 75]], //     extreme+ — dark purple (NOAA top end)
];

// Wind Chill colour ramp (°C), ASCENDING (interpStops requires it): coldest →
// comfortable. Progressively colder = deeper blue/indigo.
const COLD_STOPS: Array<[number, RGB]> = [
  [-40, [20, 18, 84]], //    extreme+ — near-black indigo
  [-30, [37, 52, 148]], //   extreme — indigo
  [-20, [34, 94, 168]], //   severe — dark blue
  [-10, [49, 130, 189]], //  very cold — deep blue
  [0, [120, 198, 230]], //   cold — blue
  [10, [199, 233, 245]], //  cool — pale blue
  [18, [240, 240, 235]], //  comfortable — neutral
];

function interpStops(stops: Array<[number, RGB]>, v: number): RGB {
  if (v <= stops[0][0]) return stops[0][1];
  if (v >= stops[stops.length - 1][0]) return stops[stops.length - 1][1];
  for (let i = 0; i < stops.length - 1; i++) {
    const [a, ca] = stops[i];
    const [b, cb] = stops[i + 1];
    if (v >= a && v <= b) {
      const t = (v - a) / (b - a);
      return [
        Math.round(ca[0] + t * (cb[0] - ca[0])),
        Math.round(ca[1] + t * (cb[1] - ca[1])),
        Math.round(ca[2] + t * (cb[2] - ca[2])),
      ];
    }
  }
  return stops[stops.length - 1][1];
}

// RGBA for the active metric. Comfortable values stay translucent so the
// basemap/labels show through; hazardous values are nearly opaque.
function metricColor(metric: MapMetric, value: number): [number, number, number, number] {
  if (metric === "cold") {
    const [r, g, b] = interpStops(COLD_STOPS, value);
    return [r, g, b, value > 10 ? 140 : 210];
  }
  const [r, g, b] = interpStops(HEAT_STOPS, value);
  return [r, g, b, value < 27 ? 150 : 210];
}

// --- Classification (US NWS) — shared with the dashboard legend & sidebar. ---
export interface ClassBand {
  label: string;
  range: string;
  color: string; // hex swatch (legend); roughly samples the ramp
}

// Heat Index classes (°C) — exact NWS thresholds, high → low.
export const HEAT_CLASSES: ClassBand[] = [
  { label: "Danger extrême", range: "> 51°C", color: "#5e0b4b" },
  { label: "Danger", range: "40–51°C", color: "#e3251c" },
  { label: "Prudence extrême", range: "33–39°C", color: "#fca12c" },
  { label: "Prudence", range: "27–32°C", color: "#ffeb84" },
  { label: "Risque faible", range: "< 27°C", color: "#c7e9b4" },
];

// Wind Chill classes (°C) — cold-stress / frostbite risk, cold → mild.
export const COLD_CLASSES: ClassBand[] = [
  { label: "Extrême", range: "< -28°C", color: "#253494" },
  { label: "Très froid", range: "-28 … -10°C", color: "#225ea8" },
  { label: "Froid", range: "-10 … 0°C", color: "#4292c6" },
  { label: "Frais", range: "0 … 10°C", color: "#c7e9f5" },
  { label: "Confort", range: "> 10°C", color: "#f0f0eb" },
];

export function heatIndexClass(c: number): ClassBand {
  if (c >= 51) return HEAT_CLASSES[0];
  if (c >= 40) return HEAT_CLASSES[1];
  if (c >= 33) return HEAT_CLASSES[2];
  if (c >= 27) return HEAT_CLASSES[3];
  return HEAT_CLASSES[4];
}

export function windChillClass(c: number): ClassBand {
  if (c < -28) return COLD_CLASSES[0];
  if (c < -10) return COLD_CLASSES[1];
  if (c < 0) return COLD_CLASSES[2];
  if (c < 10) return COLD_CLASSES[3];
  return COLD_CLASSES[4];
}

// A Sedona H3 hexagon feature carrying the multi-day forecast.
type HexFeature = Feature<Geometry, GridCellProperties>;

// Forecast for one hexagon at the selected day (falls back to day 0 / cell-level).
const cellForecast = (props: GridCellProperties, day: number): ForecastDay | undefined =>
  props.forecasts?.[day] ?? props.forecasts?.[0];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function HeatMap({ geojson, selectedDay, metric, onCellClick }: HeatMapProps) {
  // Sedona H3 hexagons coloured by the selected forecast day + metric — 2D choropleth.
  const layers = useMemo(
    () => [
      new GeoJsonLayer<GridCellProperties>({
        id: `metric-choropleth-${metric}-${selectedDay}`,
        data: (geojson?.features ?? []) as unknown as HexFeature[],
        pickable: true,
        filled: true,
        stroked: false, // borderless -> hexes blend into a smooth continuous field
        getFillColor: (f: HexFeature) => {
          const fc = cellForecast(f.properties, selectedDay);
          const value = metric === "cold" ? fc?.wind_chill : fc?.heat_index;
          return metricColor(metric, value ?? (metric === "cold" ? 18 : 18));
        },
        updateTriggers: {
          getFillColor: [selectedDay, metric],
        },
        onClick: (info) => {
          if (onCellClick && info.object) {
            onCellClick(info.object.properties.lat, info.object.properties.lon);
          }
        },
      }),
    ],
    [geojson, selectedDay, metric, onCellClick],
  );

  // Hover tooltip — both metrics, with the active one classified per NWS.
  const getTooltip = ({ object }: PickingInfo<HexFeature>) => {
    if (!object) return null;
    const p = object.properties;
    const fc = cellForecast(p, selectedDay);
    const hi = fc?.heat_index ?? 0;
    const wc = fc?.wind_chill ?? 0;
    const band = metric === "cold" ? windChillClass(wc) : heatIndexClass(hi);
    const heatStyle = metric === "heat" ? "font-weight:600" : "opacity:0.7";
    const coldStyle = metric === "cold" ? "font-weight:600" : "opacity:0.7";
    return {
      html: `
        <div style="font-family:system-ui,sans-serif;min-width:180px">
          <div style="font-weight:600;margin-bottom:4px">
            ${p.lat.toFixed(2)}°N, ${p.lon.toFixed(2)}°E
          </div>
          <div style="${heatStyle}">Indice de Chaleur : <b>${hi.toFixed(1)}°C</b></div>
          <div style="${coldStyle}">Refroidissement Éolien : <b>${wc.toFixed(1)}°C</b></div>
          <div style="margin-top:4px;display:flex;align-items:center;gap:6px">
            <span style="width:10px;height:10px;border-radius:2px;background:${band.color};display:inline-block"></span>
            <b>${band.label}</b> <span style="opacity:0.6">(${band.range})</span>
          </div>
        </div>`,
      style: {
        backgroundColor: "rgba(255,255,255,0.95)",
        color: "#222",
        borderRadius: "6px",
        padding: "8px 10px",
        boxShadow: "0 2px 8px rgba(0,0,0,0.2)",
        fontSize: "12px",
      },
    };
  };

  return (
    <Box sx={{ height: "100%", width: "100%", position: "absolute", inset: 0, zIndex: 0 }}>
      <DeckGL
        initialViewState={INITIAL_VIEW_STATE}
        controller
        layers={layers}
        getTooltip={getTooltip}
      >
        <Map mapStyle={MAP_STYLE} reuseMaps />
      </DeckGL>
    </Box>
  );
}
