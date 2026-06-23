"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import dynamic from "next/dynamic";
import {
  Box,
  Card,
  Typography,
  Divider,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
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
} from "@mui/material";

import ExpandLess from "@mui/icons-material/ExpandLess";
import ExpandMore from "@mui/icons-material/ExpandMore";
import ThermostatIcon from "@mui/icons-material/Thermostat";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import WaterDropIcon from "@mui/icons-material/WaterDrop";
import WhatshotIcon from "@mui/icons-material/Whatshot";

import type { GeoJSONData, GridCellProperties, ForecastDay } from "@/components/map/HeatMap";

const DynamicHeatMap = dynamic(() => import("@/components/map/HeatMap"), {
  ssr: false,
  loading: () => (
    <Box sx={{ display: "flex", height: "100%", alignItems: "center", justifyContent: "center" }}>
      <CircularProgress color="primary" />
    </Box>
  ),
});

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const MOROCCO_CITIES: Array<{ name: string; lat: number; lon: number }> = [
  { name: "Casablanca",  lat: 33.5731, lon: -7.5898 },
  { name: "Rabat",       lat: 34.0209, lon: -6.8416 },
  { name: "Marrakech",   lat: 31.6295, lon: -7.9811 },
  { name: "Agadir",      lat: 30.4278, lon: -9.5981 },
  { name: "Taroudant",   lat: 30.4728, lon: -8.8732 },
  { name: "Fès",         lat: 34.0331, lon: -5.0003 },
  { name: "Tanger",      lat: 35.7595, lon: -5.8340 },
  { name: "Meknès",      lat: 33.8920, lon: -5.5510 },
  { name: "Oujda",       lat: 34.6814, lon: -1.9086 },
  { name: "Kénitra",     lat: 34.2610, lon: -6.5802 },
  { name: "Tétouan",     lat: 35.5889, lon: -5.3626 },
  { name: "Safi",        lat: 32.2994, lon: -9.2372 },
  { name: "Mohammédia",  lat: 33.3093, lon: -8.4552 },
  { name: "Béni Mellal", lat: 32.3373, lon: -6.3498 },
  { name: "Nador",       lat: 35.1667, lon: -2.9333 },
  { name: "Taza",        lat: 34.2155, lon: -4.0120 },
  { name: "Settat",      lat: 33.0010, lon: -7.6166 },
  { name: "Khouribga",   lat: 32.8811, lon: -6.9063 },
  { name: "Errachidia",  lat: 31.9314, lon: -4.4244 },
  { name: "Laâyoune",    lat: 27.1525, lon: -13.2003 },
  { name: "Al Hoceïma",  lat: 35.2442, lon: -3.9317 },
  { name: "Essaouira",   lat: 31.5125, lon: -9.7700 },
  { name: "Guelmim",     lat: 28.9884, lon: -10.0633 },
];

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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const GRID_LAT_NORTH = 36.0;
const GRID_LAT_SOUTH = 27.0;
const GRID_LON_WEST = -17.0;
const GRID_ROWS = 37;
const GRID_COLS = 65;
const CELL_SIZE = (GRID_LAT_NORTH - GRID_LAT_SOUTH) / GRID_ROWS; // ~0.243

function nearestGridRowCol(lat: number, lon: number): [number, number] {
  const row = Math.round((GRID_LAT_NORTH - lat) / CELL_SIZE);
  const col = Math.round((lon - GRID_LON_WEST) / CELL_SIZE);
  return [Math.max(0, Math.min(GRID_ROWS - 1, row)), Math.max(0, Math.min(GRID_COLS - 1, col))];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function Dashboard() {
  const [geojson, setGeojson] = useState<GeoJSONData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedDayIndex, setSelectedDayIndex] = useState<number>(0);
  const [filterLevel, setFilterLevel] = useState<string>("all");
  const [expandedRegion, setExpandedRegion] = useState<number | null>(null);

  // ---- Load GeoJSON ----
  useEffect(() => {
    fetch("/data/today_alerts.geojson")
      .then((res) => res.json())
      .then((data: GeoJSONData) => {
        setGeojson(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error loading geojson:", err);
        setLoading(false);
      });
  }, []);

  // ---- Build a row,col lookup index ----
  const cellIndex: Map<string, GridCellProperties> = useMemo(() => {
    const idx = new Map<string, GridCellProperties>();
    if (!geojson) return idx;
    for (const feature of geojson.features) {
      const p = feature.properties;
      idx.set(`${p.row},${p.col}`, p);
    }
    return idx;
  }, [geojson]);

  // ---- City display data from grid cells ----
  interface CityDisplay {
    id: number;
    name: string;
    coords: [number, number];
    alert: string;
    temp: number;
    tmin: number;
    rh: number;
    heat_index: number;
    severity: number;
    date: string;
  }

  const cityRegions: CityDisplay[] = useMemo(() => {
    if (!geojson) return [];

    return MOROCCO_CITIES.map((city, index) => {
      const [r, c] = nearestGridRowCol(city.lat, city.lon);
      const key = `${r},${c}`;
      const cell = cellIndex.get(key);

      let forecast: ForecastDay | null = null;
      if (cell && cell.forecasts[selectedDayIndex]) {
        forecast = cell.forecasts[selectedDayIndex];
      } else if (cell && cell.forecasts.length > 0) {
        forecast = cell.forecasts[cell.forecasts.length - 1];
      }

      return {
        id: index,
        name: city.name,
        coords: [city.lat, city.lon] as [number, number],
        alert: forecast?.alert_level || "none",
        temp: forecast?.tmax ?? 0,
        tmin: forecast?.tmin ?? 0,
        rh: forecast?.rh ?? 0,
        heat_index: forecast?.heat_index ?? 0,
        severity: forecast?.severity ?? 0,
        date: forecast?.date ?? "",
      };
    });
  }, [geojson, cellIndex, selectedDayIndex]);

  // ---- Filtered list ----
  const displayRegions: CityDisplay[] = useMemo(() => {
    if (filterLevel === "all") return cityRegions;
    return cityRegions.filter((r) => r.alert === filterLevel);
  }, [cityRegions, filterLevel]);

  // ---- Day labels ----
  const dayLabels: string[] = useMemo(() => {
    if (!geojson || geojson.features.length === 0) return [];
    const first = geojson.features[0].properties;
    return first.forecasts.map((f) => {
      const d = new Date(f.date + "T12:00:00Z");
      return d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" });
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

  // ---- /alerts/point API call on map click ----
  const handleCellClick = useCallback(async (lat: number, lon: number) => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const res = await fetch(`${apiBase}/alerts/point?lat=${lat}&lon=${lon}`);
      if (res.ok) {
        const data = await res.json();
        console.log("Point forecast:", data);
      }
    } catch (err) {
      console.log("Point API call (expected if backend not running):", err);
    }
  }, []);

  // ---- Severity color ----
  const severityChipColor = (severity: number): "success" | "warning" | "error" | "default" => {
    if (severity > 5) return "error";
    if (severity > 2) return "warning";
    if (severity > 0) return "warning";
    return "success";
  };

  // ---- Summary counts ----
  const alertCounts = useMemo(() => {
    const counts = { red: 0, orange: 0, yellow: 0, none: 0 };
    for (const r of cityRegions) {
      counts[r.alert as keyof typeof counts]++;
    }
    return counts;
  }, [cityRegions]);

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
          onCellClick={handleCellClick}
        />

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
          <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ mb: 0.5 }}>
            Indice de Chaleur
          </Typography>
          {(["red", "orange", "yellow", "none"] as const).map((level) => (
            <Box key={level} sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <Box
                {...{
                  sx: {
                    width: 16,
                    height: 16,
                    borderRadius: "2px",
                    bgcolor: alertColors[level],
                    opacity: alertColors[level] === "#e0e0e0" ? 0.4 : 0.7,
                  },
                }}
              />
              <Typography variant="caption" color="text.secondary">
                {alertLabels[level]}
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
              <Typography variant="body2" color="primary.main" sx={{ fontWeight: 600 }}>
                {selectedDayIndex === 0
                  ? `Aujourd'hui — ${dayLabels[selectedDayIndex]}`
                  : `J+${selectedDayIndex} — ${dayLabels[selectedDayIndex]}`}
              </Typography>
              <Chip
                {...{
                  size: "small",
                  label: `${alertCounts.red + alertCounts.orange + alertCounts.yellow} alerte(s)`,
                  color:
                    alertCounts.red > 0
                      ? "error"
                      : alertCounts.orange > 0
                        ? "warning"
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
                      bgcolor: selectedDayIndex === index ? "primary.main" : "transparent",
                      color: selectedDayIndex === index ? "#fff !important" : "text.secondary",
                      "&:hover": {
                        bgcolor:
                          selectedDayIndex === index ? "primary.dark" : "action.hover",
                      },
                    },
                  }}
                >
                  {index === 0 ? `Auj.` : `J+${index}`}
                </Button>
              ))}
            </ButtonGroup>

            <Box sx={{ display: "flex", gap: 1 }}>
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
        {/* Header */}
        <Box sx={{ p: 2, bgcolor: "primary.dark", color: "primary.light" }}>
          <Typography variant="h4" sx={{ color: "white" }}>
            Vague de Chaleur — Maroc
          </Typography>
          <Typography variant="subtitle2">
            Système National de Surveillance
          </Typography>
        </Box>

        {/* Summary chips */}
        <Box sx={{ px: 2, py: 1.5, display: "flex", gap: 1, flexWrap: "wrap", borderBottom: "1px solid", borderColor: "divider" }}>
          <Chip size="small" label={`🔴 ${alertCounts.red} Extrême`} color="error" variant="outlined" />
          <Chip size="small" label={`🟠 ${alertCounts.orange} Sévère`} color="warning" variant="outlined" />
          <Chip size="small" label={`🟡 ${alertCounts.yellow} Modérée`} color="default" variant="outlined" />
        </Box>

        {/* Filter */}
        <Box sx={{ p: 2, borderBottom: "1px solid", borderColor: "divider" }}>
          <FormControl fullWidth size="small">
            <InputLabel>Niveau d&apos;Alerte</InputLabel>
            <Select
              label="Niveau d'Alerte"
              value={filterLevel}
              onChange={(e) => setFilterLevel(e.target.value)}
            >
              <MenuItem value="all">(Tous les Niveaux)</MenuItem>
              <MenuItem value="red">🔴 Alerte Extrême</MenuItem>
              <MenuItem value="orange">🟠 Alerte Sévère</MenuItem>
              <MenuItem value="yellow">🟡 Alerte Modérée</MenuItem>
              <MenuItem value="none">⚪ Aucune Alerte</MenuItem>
            </Select>
          </FormControl>
        </Box>

        {/* City list */}
        <Box sx={{ flexGrow: 1, overflowY: "auto", p: 2, bgcolor: "grey.50" }}>
          <Typography
            variant="subtitle2"
            color="text.secondary"
            sx={{ mb: 1, ml: 1 }}
          >
            VILLES {displayRegions.length > 0 ? `(${displayRegions.length})` : ""}
          </Typography>

          {loading ? (
            <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
              <CircularProgress size={32} />
            </Box>
          ) : displayRegions.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ textAlign: "center", py: 4 }}>
              Aucune ville ne correspond au filtre.
            </Typography>
          ) : (
            <List sx={{ p: 0 }}>
              {displayRegions.map((region) => (
                <Card
                  key={region.id}
                  {...{
                    sx: {
                      mb: 1,
                      overflow: "hidden",
                      borderLeft: "6px solid",
                      borderLeftColor: alertColors[region.alert],
                      boxShadow: region.alert !== "none" ? 1 : 0,
                    },
                  }}
                >
                  <ListItemButton
                    onClick={() => toggleRegion(region.id)}
                    sx={{ p: 1.5 }}
                  >
                    <ListItemIcon sx={{ minWidth: 36 }}>
                      {region.alert !== "none" ? (
                        <WarningAmberIcon sx={{ color: alertColors[region.alert] }} />
                      ) : (
                        <InfoOutlinedIcon color="disabled" />
                      )}
                    </ListItemIcon>
                    <ListItemText
                      primary={region.name}
                      primaryTypographyProps={{ fontWeight: 600, variant: "body2" }}
                    />
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1, mr: 2 }}>
                      {region.alert !== "none" && (
                        <Chip
                          size="small"
                          label={`${Math.round(region.temp)}°C`}
                          color={severityChipColor(region.severity)}
                          variant="outlined"
                        />
                      )}
                    </Box>
                    {expandedRegion === region.id ? <ExpandLess /> : <ExpandMore />}
                  </ListItemButton>

                  <Collapse in={expandedRegion === region.id} timeout="auto" unmountOnExit>
                    <Divider />
                    <Box sx={{ p: 2, bgcolor: "background.paper" }}>
                      <Grid container spacing={1.5}>
                        <Grid size={6}>
                          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                            <ThermostatIcon fontSize="small" color="error" />
                            <Typography variant="body2" color="text.secondary">
                              T<sub>max</sub>
                            </Typography>
                          </Box>
                          <Typography variant="h6" fontWeight={700}>
                            {region.temp.toFixed(1)}°C
                          </Typography>
                        </Grid>
                        <Grid size={6}>
                          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                            <ThermostatIcon fontSize="small" color="info" />
                            <Typography variant="body2" color="text.secondary">
                              T<sub>min</sub>
                            </Typography>
                          </Box>
                          <Typography variant="h6" fontWeight={700}>
                            {region.tmin.toFixed(1)}°C
                          </Typography>
                        </Grid>
                        <Grid size={6}>
                          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                            <WhatshotIcon fontSize="small" color="warning" />
                            <Typography variant="body2" color="text.secondary">
                              Heat Index
                            </Typography>
                          </Box>
                          <Typography variant="h6" fontWeight={700}>
                            {region.heat_index.toFixed(1)}°C
                          </Typography>
                        </Grid>
                        <Grid size={6}>
                          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                            <WaterDropIcon fontSize="small" color="primary" />
                            <Typography variant="body2" color="text.secondary">
                              Humidité
                            </Typography>
                          </Box>
                          <Typography variant="h6" fontWeight={700}>
                            {region.rh.toFixed(0)}%
                          </Typography>
                        </Grid>
                      </Grid>

                      {region.severity > 0 && (
                        <Box sx={{ mt: 1.5 }}>
                          <Chip
                            size="small"
                            label={alertLabels[region.alert]}
                            sx={{
                              bgcolor: alertColors[region.alert],
                              color: region.alert === "yellow" ? "#333" : "#fff",
                              fontWeight: 600,
                            }}
                          />
                          <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 0.5 }}>
                            Sévérité: +{region.severity.toFixed(1)}°C au-dessus de la normale
                          </Typography>
                        </Box>
                      )}
                    </Box>
                  </Collapse>
                </Card>
              ))}
            </List>
          )}
        </Box>
      </Box>
    </Box>
  );
}
