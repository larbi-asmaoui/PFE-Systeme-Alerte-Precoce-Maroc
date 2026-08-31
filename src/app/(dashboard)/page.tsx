"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import dynamic from "next/dynamic";
import {
  Box,
  Card,
  Typography,
  Divider,
  Button,
  ButtonGroup,
  List,
  ListItemButton,
  ListItemText,
  ListItemIcon,
  Collapse,
  Paper,
  CircularProgress,
  Grid,
  Chip,
  ToggleButton,
  ToggleButtonGroup,
} from "@mui/material";

import ExpandLess from "@mui/icons-material/ExpandLess";
import ExpandMore from "@mui/icons-material/ExpandMore";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import AcUnitIcon from "@mui/icons-material/AcUnit";
import WhatshotIcon from "@mui/icons-material/Whatshot";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import PauseIcon from "@mui/icons-material/Pause";

import type {
  GeoJSONData,
  GridCellProperties,
  ForecastDay,
  MapMetric,
  MapSource,
} from "@/components/map/HeatMap";
import {
  HEAT_CLASSES,
  COLD_CLASSES,
  heatIndexClass,
  windChillClass,
} from "@/components/map/HeatMap";

// Data source → static GeoJSON produced by each pipeline.
const SOURCE_FILES: Record<MapSource, string> = {
  stations: "/data/stations_forecast.geojson", // Pipeline A — GSOD stations (Open-Meteo + GRU)
  grid: "/data/today_alerts.geojson", // Pipeline B — ERA5-Land national surface
};

// In-memory cache of the (already-expanded) GeoJSON per source, so flipping the
// source toggle is instant instead of re-fetching + re-parsing the 9 MB grid.
const GEOJSON_CACHE = new Map<MapSource, GeoJSONData>();

const DynamicHeatMap = dynamic(() => import("@/components/map/HeatMap"), {
  ssr: false,
  loading: () => (
    <Box
      sx={{
        display: "flex",
        height: "100%",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <CircularProgress color="primary" />
    </Box>
  ),
});

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const MOROCCO_CITIES: Array<{ name: string; lat: number; lon: number }> = [
  { name: "Casablanca", lat: 33.5731, lon: -7.5898 },
  { name: "Rabat", lat: 34.0209, lon: -6.8416 },
  { name: "Marrakech", lat: 31.6295, lon: -7.9811 },
  { name: "Agadir", lat: 30.4278, lon: -9.5981 },
  { name: "Taroudant", lat: 30.4728, lon: -8.8732 },
  { name: "Fès", lat: 34.0331, lon: -5.0003 },
  { name: "Tanger", lat: 35.7595, lon: -5.834 },
  { name: "Meknès", lat: 33.892, lon: -5.551 },
  { name: "Oujda", lat: 34.6814, lon: -1.9086 },
  { name: "Kénitra", lat: 34.261, lon: -6.5802 },
  { name: "Tétouan", lat: 35.5889, lon: -5.3626 },
  { name: "Safi", lat: 32.2994, lon: -9.2372 },
  { name: "Mohammédia", lat: 33.3093, lon: -8.4552 },
  { name: "Béni Mellal", lat: 32.3373, lon: -6.3498 },
  { name: "Nador", lat: 35.1667, lon: -2.9333 },
  { name: "Taza", lat: 34.2155, lon: -4.012 },
  { name: "Settat", lat: 33.001, lon: -7.6166 },
  { name: "Khouribga", lat: 32.8811, lon: -6.9063 },
  { name: "Errachidia", lat: 31.9314, lon: -4.4244 },
  { name: "Laâyoune", lat: 27.1525, lon: -13.2003 },
  { name: "Al Hoceïma", lat: 35.2442, lon: -3.9317 },
  { name: "Essaouira", lat: 31.5125, lon: -9.77 },
  { name: "Guelmim", lat: 28.9884, lon: -10.0633 },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
// Nearest hexagon to a city, by squared lat/lon distance over the loaded cells.
function nearestCell(
  features: GeoJSONData["features"],
  lat: number,
  lon: number,
): GridCellProperties | null {
  let best: GridCellProperties | null = null;
  let bestD = Infinity;
  for (const f of features) {
    const p = f.properties;
    const d = (p.lat - lat) ** 2 + (p.lon - lon) ** 2;
    if (d < bestD) {
      bestD = d;
      best = p;
    }
  }
  return best;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function Dashboard() {
  const [geojson, setGeojson] = useState<GeoJSONData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [source, setSource] = useState<MapSource>("stations");
  const [selectedDayIndex, setSelectedDayIndex] = useState<number>(0);
  const [metric, setMetric] = useState<MapMetric>("heat");
  const [atRiskOnly, setAtRiskOnly] = useState<boolean>(false);
  const [expandedRegion, setExpandedRegion] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);

  // ---- Load GeoJSON for the active source (stations vs national grid) ----
  useEffect(() => {
    // Instant path: already fetched + expanded this source once this session.
    const cached = GEOJSON_CACHE.get(source);
    if (cached) {
      setGeojson(cached);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    fetch(SOURCE_FILES[source])
      .then((res) => res.json())
      .then((data: GeoJSONData) => {
        // Expand Stage 2's compact per-day arrays (hi/wc/sev/lvl + top-level
        // dates) into ForecastDay[] so the rest of the UI stays unchanged.
        const dates = data.dates ?? [];
        for (const f of data.features) {
          const p = f.properties;
          if (!p.forecasts && p.sev) {
            p.forecasts = p.sev.map((s, i) => ({
              day: i,
              date: dates[i] ?? "",
              heat_index: p.hi?.[i] ?? 0,
              wind_chill: p.wc?.[i] ?? 0,
              severity: s,
              alert_level: p.lvl?.[i] ?? "none",
            }));
          }
        }
        GEOJSON_CACHE.set(source, data);
        if (cancelled) return;
        setGeojson(data);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        console.error("Error loading geojson:", err);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [source]);

  // ---- City display data from grid cells ----
  interface CityDisplay {
    id: number;
    name: string;
    coords: [number, number];
    alert: string;
    heat_index: number;
    wind_chill: number;
    severity: number;
    date: string;
  }

  const pickForecast = useCallback(
    (props: GridCellProperties | null): ForecastDay | null => {
      if (!props?.forecasts?.length) return null;
      return (
        props.forecasts[selectedDayIndex] ??
        props.forecasts[props.forecasts.length - 1]
      );
    },
    [selectedDayIndex],
  );

  // Resolve each sidebar row to its underlying feature ONCE per dataset. For the
  // grid this runs the O(cities × cells) nearest-cell search a single time, not
  // on every slider tick — the day only re-picks a forecast from these props.
  const regionSources: Array<{
    id: number;
    name: string;
    props: GridCellProperties;
  }> = useMemo(() => {
    if (!geojson) return [];
    if (source === "stations") {
      return geojson.features.map((f, index) => ({
        id: index,
        name: f.properties.station_name || `Station ${index + 1}`,
        props: f.properties,
      }));
    }
    return MOROCCO_CITIES.map((city, index) => {
      const props = nearestCell(geojson.features, city.lat, city.lon);
      return {
        id: index,
        name: city.name,
        props:
          props ?? ({ lat: city.lat, lon: city.lon } as GridCellProperties),
      };
    });
  }, [geojson, source]);

  const cityRegions: CityDisplay[] = useMemo(() => {
    return regionSources.map(({ id, name, props }) => {
      const forecast = pickForecast(props);
      return {
        id,
        name,
        coords: [props.lat, props.lon] as [number, number],
        alert: forecast?.alert_level || "none",
        heat_index: forecast?.heat_index ?? 0,
        wind_chill: forecast?.wind_chill ?? 0,
        severity: forecast?.severity ?? 0,
        date: forecast?.date ?? "",
      };
    });
  }, [regionSources, pickForecast]);

  // ---- Metric-aware helpers (active metric drives value / class / risk) ----
  const cityValue = useCallback(
    (r: CityDisplay) => (metric === "cold" ? r.wind_chill : r.heat_index),
    [metric],
  );
  const cityBand = useCallback(
    (r: CityDisplay) =>
      metric === "cold"
        ? windChillClass(r.wind_chill)
        : heatIndexClass(r.heat_index),
    [metric],
  );
  // "At risk" = beyond the comfortable/low-risk class for the active metric.
  const cityAtRisk = useCallback(
    (r: CityDisplay) =>
      metric === "cold" ? r.wind_chill < 0 : r.heat_index >= 27,
    [metric],
  );

  // ---- Filtered + sorted list (most at-risk first) ----
  const displayRegions: CityDisplay[] = useMemo(() => {
    const list = atRiskOnly ? cityRegions.filter(cityAtRisk) : [...cityRegions];
    return list.sort((a, b) =>
      metric === "cold"
        ? cityValue(a) - cityValue(b)
        : cityValue(b) - cityValue(a),
    );
  }, [cityRegions, atRiskOnly, metric, cityAtRisk, cityValue]);

  // ---- Day labels ----
  const dayLabels: string[] = useMemo(() => {
    if (!geojson || geojson.features.length === 0) return [];
    const first = geojson.features[0].properties;
    return first.forecasts.map((f) => {
      const d = new Date(f.date + "T12:00:00Z");
      return d.toLocaleDateString("fr-FR", {
        weekday: "short",
        day: "numeric",
        month: "short",
      });
    });
  }, [geojson]);

  // ---- Handlers ----
  const toggleRegion = (id: number) => {
    setExpandedRegion(expandedRegion === id ? null : id);
  };

  const handlePrevDay = () =>
    setSelectedDayIndex((prev) => Math.max(0, prev - 1));
  const handleNextDay = () =>
    setSelectedDayIndex((prev) => Math.min(dayLabels.length - 1, prev + 1));

  // ---- Playback: animate the forecast day every second while playing ----
  useEffect(() => {
    if (!isPlaying || dayLabels.length === 0) return;
    const id = setInterval(() => {
      setSelectedDayIndex((prev) => (prev + 1) % dayLabels.length);
    }, 1000);
    return () => clearInterval(id);
  }, [isPlaying, dayLabels.length]);

  // ---- /alerts/point API call on map click ----
  const handleCellClick = useCallback(async (lat: number, lon: number) => {
    try {
      const apiBase =
        process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const res = await fetch(`${apiBase}/alerts/point?lat=${lat}&lon=${lon}`);
      if (res.ok) {
        const data = await res.json();
        console.log("Point forecast:", data);
      }
    } catch (err) {
      console.log("Point API call (expected if backend not running):", err);
    }
  }, []);

  // ---- Summary by the active metric's NWS classes (only non-safe tiers) ----
  const riskSummary = useMemo(() => {
    const classes = metric === "heat" ? HEAT_CLASSES : COLD_CLASSES;
    const counts = new Map<string, number>();
    for (const r of cityRegions)
      counts.set(cityBand(r).label, (counts.get(cityBand(r).label) ?? 0) + 1);
    // drop the lowest/safe tier (last entry of each class list) from the chips
    return classes
      .slice(0, -1)
      .map((c) => ({ ...c, count: counts.get(c.label) ?? 0 }));
  }, [cityRegions, metric, cityBand]);

  const atRiskCount = useMemo(
    () => cityRegions.filter(cityAtRisk).length,
    [cityRegions, cityAtRisk],
  );

  // ---- KPI strip: headline numbers for the selected day + active metric ----
  const kpis = useMemo(() => {
    const total = cityRegions.length;
    if (total === 0) {
      return { total, atRisk: 0, peakLabel: "—", peakName: "—", riskPct: 0 };
    }
    // "Peak" = hottest (heat) or coldest (cold) entity of the day.
    const peak = cityRegions.reduce((acc, r) =>
      metric === "cold"
        ? r.wind_chill < acc.wind_chill
          ? r
          : acc
        : r.heat_index > acc.heat_index
          ? r
          : acc,
    );
    const peakVal = metric === "cold" ? peak.wind_chill : peak.heat_index;
    return {
      total,
      atRisk: atRiskCount,
      peakLabel: `${Math.round(peakVal)}°C`,
      peakName: peak.name,
      riskPct: Math.round((atRiskCount / total) * 100),
    };
  }, [cityRegions, metric, atRiskCount]);

  // Sidebar wording adapts to the active source.
  const entityLabel = source === "stations" ? "STATIONS" : "VILLES";
  const entityNoun = source === "stations" ? "station" : "ville";

  return (
    <Box
      {...{
        sx: {
          display: "flex",
          flexDirection: { xs: "column", md: "row" },
          height: "calc(100vh - 88px)",
          overflow: "hidden",
          m: -2,
        },
      }}
    >
      {/* ========================================== */}
      {/* LEFT SIDE: FULL SCREEN MAP AREA            */}
      {/* ========================================== */}
      <Box sx={{ flexGrow: 1, position: "relative", bgcolor: "#e5e9f0" }}>
        <DynamicHeatMap
          geojson={geojson}
          selectedDay={selectedDayIndex}
          metric={metric}
          sourceType={source}
          onCellClick={handleCellClick}
        />

        {/* SOURCE TOGGLE — Stations (points) vs National surface (ERA5-Land grid) */}
        <Paper
          elevation={3}
          sx={{
            position: "absolute",
            top: 16,
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 1000,
            borderRadius: 2,
            overflow: "hidden",
          }}
        >
          <ToggleButtonGroup
            value={source}
            exclusive
            size="small"
            onChange={(_e, val) => val && setSource(val as MapSource)}
          >
            <ToggleButton
              value="stations"
              sx={{ textTransform: "none", px: 1.5, gap: 0.5 }}
            >
              Stations
            </ToggleButton>
            <ToggleButton
              value="grid"
              sx={{ textTransform: "none", px: 1.5, gap: 0.5 }}
            >
              National (ERA5-Land)
            </ToggleButton>
          </ToggleButtonGroup>
        </Paper>

        {/* METRIC TOGGLE — Heat Index vs Wind Chill */}
        <Paper
          elevation={3}
          sx={{
            position: "absolute",
            top: 16,
            left: 16,
            zIndex: 1000,
            borderRadius: 2,
            overflow: "hidden",
          }}
        >
          <ToggleButtonGroup
            value={metric}
            exclusive
            size="small"
            onChange={(_e, val) => val && setMetric(val as MapMetric)}
          >
            <ToggleButton
              value="heat"
              sx={{ textTransform: "none", px: 1.5, gap: 0.5 }}
            >
              <WhatshotIcon fontSize="small" color="error" />
              Heat Index
            </ToggleButton>
            <ToggleButton
              value="cold"
              sx={{ textTransform: "none", px: 1.5, gap: 0.5 }}
            >
              <AcUnitIcon fontSize="small" color="info" />
              Wind Chill Index
            </ToggleButton>
          </ToggleButtonGroup>
        </Paper>

        {/* FLOATING LEGEND */}
        <Box
          {...{
            sx: {
              position: "absolute",
              bottom: 90,
              right: 24,
              display: "flex",
              flexDirection: "column",
              gap: 0.5,
              p: 1.5,
              borderRadius: 2,
              zIndex: 1000,
              bgcolor: "rgba(255,255,255,0.85)",
              backdropFilter: "blur(4px)",
              boxShadow: 1,
            },
          }}
        >
          <Typography
            variant="caption"
            fontWeight={600}
            color="text.secondary"
            sx={{ mb: 0.5 }}
          >
            {metric === "heat" ? "Heat Index (NWS)" : "Wind Chill Index"}
          </Typography>
          {(metric === "heat" ? HEAT_CLASSES : COLD_CLASSES).map((band) => (
            <Box
              key={band.label}
              sx={{ display: "flex", alignItems: "center", gap: 1 }}
            >
              <Box
                sx={{
                  width: 16,
                  height: 16,
                  borderRadius: "2px",
                  bgcolor: band.color,
                  border: "1px solid rgba(0,0,0,0.12)",
                }}
              />
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ minWidth: 110 }}
              >
                {band.label}
              </Typography>
              <Typography variant="caption" color="text.disabled">
                {band.range}
              </Typography>
            </Box>
          ))}
        </Box>

        {/* FORECAST TIME SCRUBBER */}
        <Box
          {...{
            sx: {
              position: "absolute",
              bottom: 16,
              left: 16,
              right: 16,
              zIndex: 1000,
              display: "flex",
              flexDirection: "column",
              alignItems: "flex-start",
            },
          }}
        >
          {dayLabels.length > 0 && (
            <Paper
              {...{
                elevation: 3,
                sx: {
                  display: "flex",
                  alignItems: "center",
                  gap: 1,
                  px: 2,
                  py: 0.75,
                  borderBottomLeftRadius: 0,
                  borderBottomRightRadius: 0,
                  borderTopLeftRadius: 8,
                  borderTopRightRadius: 8,
                },
              }}
            >
              <AccessTimeIcon fontSize="small" color="primary" />
              <Typography
                variant="body2"
                color="primary.main"
                sx={{ fontWeight: 600 }}
              >
                {selectedDayIndex === 0
                  ? `Aujourd'hui — ${dayLabels[selectedDayIndex]}`
                  : `J+${selectedDayIndex} — ${dayLabels[selectedDayIndex]}`}
              </Typography>
              <Chip
                {...{
                  size: "small",
                  label: `${atRiskCount} ${entityNoun}${atRiskCount > 1 ? "s" : ""} à risque`,
                  color:
                    atRiskCount > 0
                      ? metric === "heat"
                        ? "error"
                        : "info"
                      : "default",
                }}
              />
            </Paper>
          )}

          <Paper
            {...{
              elevation: 4,
              sx: {
                width: "100%",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                p: 1,
                borderTopLeftRadius: 0,
                borderRadius: 2,
              },
            }}
          >
            <ButtonGroup
              {...{
                size: "small",
                sx: {
                  boxShadow: "none",
                  flexWrap: "wrap",
                  "& .MuiButton-root": {
                    borderColor: "divider",
                    textTransform: "none",
                    px: 1.5,
                    fontWeight: 600,
                    whiteSpace: "nowrap",
                    fontSize: "0.75rem",
                  },
                },
              }}
            >
              {dayLabels.map((label, index) => (
                <Button
                  key={index}
                  onClick={() => setSelectedDayIndex(index)}
                  {...{
                    sx: {
                      bgcolor:
                        selectedDayIndex === index
                          ? "primary.main"
                          : "transparent",
                      color:
                        selectedDayIndex === index
                          ? "#fff !important"
                          : "text.secondary",
                      "&:hover": {
                        bgcolor:
                          selectedDayIndex === index
                            ? "primary.dark"
                            : "action.hover",
                      },
                    },
                  }}
                >
                  {index === 0 ? `Auj.` : `J+${index}`}
                </Button>
              ))}
            </ButtonGroup>

            <Box sx={{ display: "flex", gap: 1 }}>
              <Button
                {...{
                  size: "small",
                  variant: "contained",
                  disableElevation: true,
                  onClick: () => setIsPlaying((p) => !p),
                  startIcon: isPlaying ? (
                    <PauseIcon fontSize="small" />
                  ) : (
                    <PlayArrowIcon fontSize="small" />
                  ),
                  sx: {
                    textTransform: "none",
                    fontWeight: 600,
                    px: 1.5,
                    whiteSpace: "nowrap",
                    bgcolor: isPlaying ? "warning.main" : "primary.main",
                    "&:hover": {
                      bgcolor: isPlaying ? "warning.dark" : "primary.dark",
                    },
                  },
                }}
              >
                {isPlaying ? "Pause" : "Lecture"}
              </Button>

              <ButtonGroup
                {...{
                  size: "small",
                  sx: {
                    boxShadow: "none",
                    "& .MuiButton-root": {
                      borderColor: "divider",
                      color: "text.secondary",
                    },
                  },
                }}
              >
                <Button
                  onClick={handlePrevDay}
                  disabled={selectedDayIndex === 0}
                  {...{ sx: { "&:hover": { bgcolor: "action.hover" } } }}
                >
                  <ChevronLeftIcon fontSize="small" />
                </Button>
                <Button
                  onClick={handleNextDay}
                  disabled={selectedDayIndex === dayLabels.length - 1}
                  {...{ sx: { "&:hover": { bgcolor: "action.hover" } } }}
                >
                  <ChevronRightIcon fontSize="small" />
                </Button>
              </ButtonGroup>
            </Box>
          </Paper>
        </Box>
      </Box>

      {/* ========================================== */}
      {/* RIGHT SIDE: SIDEBAR DATA PANEL             */}
      {/* ========================================== */}
      <Box
        {...{
          sx: {
            width: { xs: "100%", md: "420px" },
            height: { xs: "50%", md: "100%" },
            flexShrink: 0,
            display: "flex",
            flexDirection: "column",
            borderLeft: "1px solid",
            borderColor: "divider",
            bgcolor: "background.paper",
            zIndex: 1000,
            overflowY: "auto",
          },
        }}
      >
        {/* Header — reflects the active metric */}
        <Box
          sx={{
            px: 2.5,
            py: 2,
            color: "white",
            background:
              metric === "heat"
                ? "linear-gradient(135deg, #b3261e 0%, #7a1712 100%)"
                : "linear-gradient(135deg, #1e5fa8 0%, #10315f 100%)",
          }}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            {metric === "heat" ? <WhatshotIcon /> : <AcUnitIcon />}
            <Typography
              variant="h5"
              sx={{ color: "white", fontWeight: 700, lineHeight: 1.1 }}
            >
              {metric === "heat" ? "Vague de Chaleur" : "Vague de Froid"}
            </Typography>
          </Box>
          <Typography
            variant="h5"
            sx={{ color: "white", opacity: 0.9, mt: 0.5 }}
          >
            Maroc ·{" "}
            {dayLabels[selectedDayIndex]
              ? `Prévision ${dayLabels[selectedDayIndex]}`
              : "Système National de Surveillance"}
          </Typography>
        </Box>

        {/* KPI strip — headline numbers for the selected day */}
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            borderBottom: "1px solid",
            borderColor: "divider",
            bgcolor: "background.paper",
          }}
        >
          {[
            {
              label: entityLabel === "STATIONS" ? "Stations" : "Villes",
              value: String(kpis.total),
              sub: "suivies",
            },
            {
              label: "À risque",
              value: String(kpis.atRisk),
              sub: `${kpis.riskPct}%`,
              accent:
                kpis.atRisk > 0
                  ? metric === "heat"
                    ? "error.main"
                    : "info.main"
                  : "text.primary",
            },
            {
              label: metric === "heat" ? "Pic chaleur" : "Pic froid",
              value: kpis.peakLabel,
              sub: kpis.peakName,
              accent: metric === "heat" ? "error.main" : "info.main",
            },
          ].map((kpi, i) => (
            <Box
              key={kpi.label}
              sx={{
                px: 1.5,
                py: 1.25,
                textAlign: "center",
                borderLeft: i === 0 ? "none" : "1px solid",
                borderColor: "divider",
              }}
            >
              <Typography
                variant="h6"
                sx={{
                  fontWeight: 800,
                  lineHeight: 1.1,
                  color: kpi.accent ?? "text.primary",
                }}
              >
                {kpi.value}
              </Typography>
              <Typography
                variant="caption"
                sx={{
                  fontWeight: 600,
                  display: "block",
                  color: "text.secondary",
                }}
              >
                {kpi.label}
              </Typography>
              <Typography
                variant="caption"
                sx={{
                  color: "text.disabled",
                  display: "block",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {kpi.sub}
              </Typography>
            </Box>
          ))}
        </Box>

        {/* Summary — counts per NWS class (only non-safe tiers with cities) */}
        <Box
          sx={{
            px: 2,
            py: 1.5,
            display: "flex",
            gap: 0.75,
            flexWrap: "wrap",
            borderBottom: "1px solid",
            borderColor: "divider",
          }}
        >
          {riskSummary.filter((c) => c.count > 0).length === 0 ? (
            <Typography variant="caption" color="text.secondary">
              Aucune ville en alerte pour cette journée.
            </Typography>
          ) : (
            riskSummary
              .filter((c) => c.count > 0)
              .map((c) => (
                <Chip
                  key={c.label}
                  size="small"
                  label={`${c.count} ${c.label}`}
                  sx={{
                    bgcolor: c.color,
                    color: "#222",
                    fontWeight: 600,
                    border: "1px solid rgba(0,0,0,0.12)",
                  }}
                />
              ))
          )}
        </Box>

        {/* Filter — at-risk only toggle */}
        <Box
          sx={{
            px: 2,
            py: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: "1px solid",
            borderColor: "divider",
          }}
        >
          <Typography
            variant="subtitle2"
            color="text.secondary"
            sx={{ fontWeight: 700, letterSpacing: 0.5 }}
          >
            {entityLabel} ({displayRegions.length})
          </Typography>
          <ToggleButtonGroup
            value={atRiskOnly ? "risk" : "all"}
            exclusive
            size="small"
            onChange={(_e, val) => val && setAtRiskOnly(val === "risk")}
          >
            <ToggleButton
              value="all"
              sx={{ textTransform: "none", py: 0.25, px: 1 }}
            >
              Toutes
            </ToggleButton>
            <ToggleButton
              value="risk"
              sx={{ textTransform: "none", py: 0.25, px: 1 }}
            >
              À risque
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>

        {/* City list */}
        <Box sx={{ flexGrow: 1, overflowY: "auto", p: 2, bgcolor: "grey.50" }}>
          {loading ? (
            <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
              <CircularProgress size={32} />
            </Box>
          ) : displayRegions.length === 0 ? (
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ textAlign: "center", py: 4 }}
            >
              Aucune ville à risque pour cette journée.
            </Typography>
          ) : (
            <List sx={{ p: 0 }}>
              {displayRegions.map((region) => {
                const band = cityBand(region);
                const value = cityValue(region);
                const risky = cityAtRisk(region);
                return (
                  <Card
                    key={region.id}
                    {...{
                      sx: {
                        mb: 1,
                        overflow: "hidden",
                        borderLeft: "6px solid",
                        borderLeftColor: band.color,
                        boxShadow: risky ? 1 : 0,
                      },
                    }}
                  >
                    <ListItemButton
                      onClick={() => toggleRegion(region.id)}
                      sx={{ p: 1.5 }}
                    >
                      <ListItemIcon sx={{ minWidth: 36 }}>
                        {risky ? (
                          metric === "heat" ? (
                            <WhatshotIcon sx={{ color: band.color }} />
                          ) : (
                            <AcUnitIcon sx={{ color: band.color }} />
                          )
                        ) : (
                          <InfoOutlinedIcon color="disabled" />
                        )}
                      </ListItemIcon>
                      <ListItemText
                        primary={region.name}
                        secondary={band.label}
                        primaryTypographyProps={{
                          fontWeight: 600,
                          variant: "body2",
                        }}
                        secondaryTypographyProps={{ variant: "caption" }}
                      />
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          gap: 1,
                          mr: 1,
                        }}
                      >
                        <Chip
                          size="small"
                          label={`${Math.round(value)}°C`}
                          sx={{
                            bgcolor: band.color,
                            color: "#222",
                            fontWeight: 700,
                            border: "1px solid rgba(0,0,0,0.12)",
                          }}
                        />
                      </Box>
                      {expandedRegion === region.id ? (
                        <ExpandLess />
                      ) : (
                        <ExpandMore />
                      )}
                    </ListItemButton>

                    <Collapse
                      in={expandedRegion === region.id}
                      timeout="auto"
                      unmountOnExit
                    >
                      <Divider />
                      <Box sx={{ p: 2, bgcolor: "background.paper" }}>
                        <Grid container spacing={1.5}>
                          <Grid size={6}>
                            <Box
                              sx={{
                                display: "flex",
                                alignItems: "center",
                                gap: 0.5,
                              }}
                            >
                              <WhatshotIcon fontSize="small" color="error" />
                              <Typography
                                variant="body2"
                                color="text.secondary"
                              >
                                Heat Index
                              </Typography>
                            </Box>
                            <Typography variant="h6" fontWeight={700}>
                              {region.heat_index.toFixed(1)}°C
                            </Typography>
                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              {heatIndexClass(region.heat_index).label}
                            </Typography>
                          </Grid>
                          <Grid size={6}>
                            <Box
                              sx={{
                                display: "flex",
                                alignItems: "center",
                                gap: 0.5,
                              }}
                            >
                              <AcUnitIcon fontSize="small" color="info" />
                              <Typography
                                variant="body2"
                                color="text.secondary"
                              >
                                Wind Chill Index
                              </Typography>
                            </Box>
                            <Typography variant="h6" fontWeight={700}>
                              {region.wind_chill.toFixed(1)}°C
                            </Typography>
                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              {windChillClass(region.wind_chill).label}
                            </Typography>
                          </Grid>
                        </Grid>
                        {region.date && (
                          <Typography
                            variant="caption"
                            display="block"
                            color="text.disabled"
                            sx={{ mt: 1.5 }}
                          >
                            {region.coords[0].toFixed(2)}°N,{" "}
                            {region.coords[1].toFixed(2)}°E · {region.date}
                          </Typography>
                        )}
                      </Box>
                    </Collapse>
                  </Card>
                );
              })}
            </List>
          )}
        </Box>
      </Box>
    </Box>
  );
}
