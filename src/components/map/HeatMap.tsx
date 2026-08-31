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
  // Station source (Pipeline A): each Point feature is a monitored GSOD station.
  station_id?: string;
  station_name?: string;
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

// Which pipeline feeds the map: the ERA5-Land hex choropleth or the GSOD stations.
export type MapSource = "grid" | "stations";

interface HeatMapProps {
  geojson: GeoJSONData | null;
  selectedDay: number;
  metric: MapMetric;
  sourceType?: MapSource;
  onCellClick?: (lat: number, lon: number) => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
// Open / free MapLibre vector style (no API key) — light Carto "Positron".
const MAP_STYLE =
  "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

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
  [32, [254, 204, 92]], //   extreme caution — amber
  [41, [253, 141, 60]], //   danger — orange
  [48, [240, 59, 32]], //    danger — red
  [54, [189, 0, 38]], //     extreme danger — deep red
  [60, [94, 11, 75]], //     extreme+ — dark purple (NOAA top end)
];

// Wind Chill colour ramp (°C), ASCENDING (interpStops requires it): coldest →
// comfortable. Progressively colder = deeper blue/indigo.
const COLD_STOPS: Array<[number, RGB]> = [
  [-35, [20, 18, 84]], //    froid extrême — near-black indigo
  [-20, [37, 52, 148]], //   froid extrême onset — indigo
  [-10, [34, 94, 168]], //   froid inconfortable — dark blue
  [0, [49, 130, 189]], //    frais onset — deep blue
  [8, [120, 198, 230]], //   frais — blue
  [15, [199, 233, 245]], //  confort onset — pale blue
  [22, [240, 240, 235]], //  confort — neutral
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
function metricColor(
  metric: MapMetric,
  value: number,
): [number, number, number, number] {
  if (metric === "cold") {
    const [r, g, b] = interpStops(COLD_STOPS, value);
    return [r, g, b, value > 15 ? 140 : 210];
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

// Heat Index classes (°C) — NWS thresholds, high → low.
export const HEAT_CLASSES: ClassBand[] = [
  { label: "Danger extrême", range: "> 54°C", color: "#5e0b4b" },
  { label: "Danger", range: "41–54°C", color: "#e3251c" },
  { label: "Vigilance accrue", range: "32–41°C", color: "#fca12c" },
  { label: "Vigilance", range: "27–32°C", color: "#ffeb84" },
  { label: "Risque faible", range: "< 27°C", color: "#c7e9b4" },
];

// Wind Chill classes (°C) — cold-stress risk, cold → mild.
export const COLD_CLASSES: ClassBand[] = [
  { label: "Froid extrême", range: "-35 … -20°C", color: "#253494" },
  { label: "Froid inconfortable", range: "-20 … 0°C", color: "#4292c6" },
  { label: "Frais", range: "0 … 15°C", color: "#c7e9f5" },
  { label: "Confort", range: "> 15°C", color: "#f0f0eb" },
];

export function heatIndexClass(c: number): ClassBand {
  if (c >= 54) return HEAT_CLASSES[0];
  if (c >= 41) return HEAT_CLASSES[1];
  if (c >= 32) return HEAT_CLASSES[2];
  if (c >= 27) return HEAT_CLASSES[3];
  return HEAT_CLASSES[4];
}

export function windChillClass(c: number): ClassBand {
  if (c < -20) return COLD_CLASSES[0];
  if (c < 0) return COLD_CLASSES[1];
  if (c < 15) return COLD_CLASSES[2];
  return COLD_CLASSES[3];
}

// A Sedona H3 hexagon feature carrying the multi-day forecast.
type HexFeature = Feature<Geometry, GridCellProperties>;

// Forecast for one hexagon at the selected day (falls back to day 0 / cell-level).
const cellForecast = (
  props: GridCellProperties,
  day: number,
): ForecastDay | undefined => props.forecasts?.[day] ?? props.forecasts?.[0];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function HeatMap({
  geojson,
  selectedDay,
  metric,
  sourceType = "grid",
  onCellClick,
}: HeatMapProps) {
  // ERA5-Land H3 hexagons (choropleth) OR GSOD stations (graduated points),
  // both coloured by the selected forecast day + metric.
  const isStations = sourceType === "stations";
  const layers = useMemo(
    () => [
      new GeoJsonLayer<GridCellProperties>({
        // Stable id per source: deck.gl then recolors via updateTriggers instead
        // of destroying + re-uploading the whole layer on each day/metric change.
        id: `layer-${sourceType}`,
        data: (geojson?.features ?? []) as unknown as HexFeature[],
        pickable: true,
        filled: true,
        // Stations: bold circles with a white outline so they read as discrete
        // points over the basemap. Grid: borderless -> smooth continuous field.
        stroked: isStations,
        getLineColor: [255, 255, 255, 230],
        lineWidthMinPixels: isStations ? 1.5 : 0,
        pointType: "circle",
        pointRadiusUnits: "pixels",
        pointRadiusMinPixels: 6,
        pointRadiusMaxPixels: 26,
        // Radius grows with how far into the alert zone the station's severity is.
        getPointRadius: (f: HexFeature) => {
          const fc = cellForecast(f.properties, selectedDay);
          return 7 + Math.max(0, fc?.severity ?? 0) * 2.2;
        },
        getFillColor: (f: HexFeature) => {
          const fc = cellForecast(f.properties, selectedDay);
          const value = metric === "cold" ? fc?.wind_chill : fc?.heat_index;
          return metricColor(metric, value ?? 18);
        },
        updateTriggers: {
          getFillColor: [selectedDay, metric],
          getPointRadius: [selectedDay, metric],
        },
        onClick: (info) => {
          if (onCellClick && info.object) {
            onCellClick(info.object.properties.lat, info.object.properties.lon);
          }
        },
      }),
    ],
    [geojson, selectedDay, metric, sourceType, isStations, onCellClick],
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
    const title = p.station_name
      ? `${p.station_name}`
      : `${p.lat.toFixed(2)}°N, ${p.lon.toFixed(2)}°E`;
    return {
      html: `
        <div style="font-family:system-ui,sans-serif;min-width:180px">
          <div style="font-weight:600;margin-bottom:4px">
            ${title}
          </div>
          <div style="${heatStyle}">Heat Index : <b>${hi.toFixed(1)}°C</b></div>
          <div style="${coldStyle}">Wind Chill Index : <b>${wc.toFixed(1)}°C</b></div>
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
    <Box
      sx={{
        height: "100%",
        width: "100%",
        position: "absolute",
        inset: 0,
        zIndex: 0,
      }}
    >
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
