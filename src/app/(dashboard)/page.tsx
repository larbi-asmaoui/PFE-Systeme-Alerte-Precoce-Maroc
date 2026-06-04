"use client";

import React, { useState, useEffect, useMemo } from "react";
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
import AirIcon from "@mui/icons-material/Air";
import WhatshotIcon from "@mui/icons-material/Whatshot";

const DynamicHeatMap = dynamic(() => import("@/components/map/HeatMap"), {
  ssr: false,
  loading: () => (
    <Box sx={{ display: "flex", height: "100%", alignItems: "center", justifyContent: "center" }}>
      <CircularProgress color="primary" />
    </Box>
  ),
});

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface ForecastDay {
  day: number;
  date: string;
  tmax: number;
  tmin: number;
  rh: number;
  heat_index: number;
  severity: number;
  alert_level: string;
}

interface CityFeature {
  id: number;
  name: string;
  coords: [number, number];
  alert_level: string;
  severity: number;
  forecasts: ForecastDay[];
}

interface DisplayRegion {
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

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
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
// Component
// ---------------------------------------------------------------------------
export default function Dashboard() {
  const [cities, setCities] = useState<CityFeature[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedDayIndex, setSelectedDayIndex] = useState<number>(0);
  const [filterLevel, setFilterLevel] = useState<string>("all");
  const [expandedRegion, setExpandedRegion] = useState<number | null>(null);

  // ---- Load GeoJSON ----
  useEffect(() => {
    fetch("/data/today_alerts.geojson")
      .then((res) => res.json())
      .then((data) => {
        if (data.features) {
          const parsed: CityFeature[] = data.features.map(
            (feature: any, index: number) => {
              const props = feature.properties;
              const coords = feature.geometry.coordinates; // [lon, lat]
              return {
                id: index,
                name: props.name || `Zone [${coords[1].toFixed(2)}, ${coords[0].toFixed(2)}]`,
                coords: [coords[1], coords[0]] as [number, number],
                alert_level: props.alert_level || "none",
                severity: props.severity ?? 0,
                forecasts: props.forecasts || [],
              };
            }
          );
          setCities(parsed);
        }
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error loading geojson:", err);
        setLoading(false);
      });
  }, []);

  // ---- Derived display regions for current day ----
  const regions: DisplayRegion[] = useMemo(() => {
    return cities.map((city) => {
      const f =
        city.forecasts[selectedDayIndex] ||
        city.forecasts[city.forecasts.length - 1] ||
        ({
          tmax: 0,
          tmin: 0,
          rh: 0,
          heat_index: 0,
          severity: 0,
          alert_level: "none",
          date: "",
        } as ForecastDay);

      return {
        id: city.id,
        name: city.name,
        coords: city.coords,
        alert: f.alert_level,
        temp: f.tmax,
        tmin: f.tmin,
        rh: f.rh,
        heat_index: f.heat_index,
        severity: f.severity,
        date: f.date,
      };
    });
  }, [cities, selectedDayIndex]);

  // ---- Filtered list ----
  const displayRegions: DisplayRegion[] = useMemo(() => {
    if (filterLevel === "all") return regions;
    return regions.filter((r) => r.alert === filterLevel);
  }, [regions, filterLevel]);

  // ---- Day labels from actual forecast dates ----
  const dayLabels: string[] = useMemo(() => {
    if (cities.length === 0) return [];
    return cities[0].forecasts.map((f) => {
      const d = new Date(f.date + "T12:00:00Z");
      return d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" });
    });
  }, [cities]);

  // ---- Handlers ----
  const toggleRegion = (id: number) => {
    setExpandedRegion(expandedRegion === id ? null : id);
  };

  const handlePrevDay = () =>
    setSelectedDayIndex((prev) => Math.max(0, prev - 1));
  const handleNextDay = () =>
    setSelectedDayIndex((prev) => Math.min(dayLabels.length - 1, prev + 1));

  // ---- Severity color for chips ----
  const severityChipColor = (severity: number): "success" | "warning" | "error" | "default" => {
    if (severity > 5) return "error";
    if (severity > 2) return "warning";
    if (severity > 0) return "warning";
    return "success";
  };

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: { xs: "column", md: "row" },
        height: "calc(100vh - 88px)",
        overflow: "hidden",
        m: -2,
      }}
    >
      {/* ========================================== */}
      {/* LEFT SIDE: FULL SCREEN MAP AREA            */}
      {/* ========================================== */}
      <Box sx={{ flexGrow: 1, position: "relative", bgcolor: "#e5e9f0" }}>
        <DynamicHeatMap regions={regions} />

        {/* FLOATING LEGEND */}
        <Box
          sx={{
            position: "absolute",
            bottom: 90,
            right: 24,
            display: "flex",
            gap: 1,
            p: 1,
            borderRadius: 8,
            zIndex: 1000,
            bgcolor: "rgba(255,255,255,0.7)",
            backdropFilter: "blur(4px)",
          }}
        >
          {(["yellow", "orange", "red"] as const).map((level) => (
            <Box key={level} sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <Box
                sx={{
                  width: 14,
                  height: 14,
                  borderRadius: "50%",
                  bgcolor: alertColors[level],
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
          sx={{
            position: "absolute",
            bottom: 16,
            left: 16,
            right: 16,
            zIndex: 1000,
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-start",
          }}
        >
          {dayLabels.length > 0 && (
            <Paper
              elevation={3}
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 1,
                px: 2,
                py: 0.75,
                borderBottomLeftRadius: 0,
                borderBottomRightRadius: 0,
                borderTopLeftRadius: 8,
                borderTopRightRadius: 8,
              }}
            >
              <AccessTimeIcon fontSize="small" color="primary" />
              <Typography variant="body2" color="primary.main" sx={{ fontWeight: 600 }}>
                {selectedDayIndex === 0
                  ? `Aujourd'hui — ${dayLabels[selectedDayIndex]}`
                  : `J+${selectedDayIndex} — ${dayLabels[selectedDayIndex]}`}
              </Typography>
              <Chip
                size="small"
                label={`${displayRegions.filter((r) => r.alert !== "none").length} alerte(s)`}
                color={
                  displayRegions.filter((r) => r.alert === "red").length > 0
                    ? "error"
                    : displayRegions.filter((r) => r.alert === "orange").length > 0
                      ? "warning"
                      : "default"
                }
              />
            </Paper>
          )}

          <Paper
            elevation={4}
            sx={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              p: 1,
              borderTopLeftRadius: 0,
              borderRadius: 2,
            }}
          >
            <ButtonGroup
              size="small"
              sx={{
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
              }}
            >
              {dayLabels.map((label, index) => (
                <Button
                  key={index}
                  onClick={() => setSelectedDayIndex(index)}
                  sx={{
                    bgcolor: selectedDayIndex === index ? "primary.main" : "transparent",
                    color: selectedDayIndex === index ? "#fff !important" : "text.secondary",
                    "&:hover": {
                      bgcolor:
                        selectedDayIndex === index ? "primary.dark" : "action.hover",
                    },
                  }}
                >
                  {index === 0 ? `Auj.` : `J+${index}`}
                </Button>
              ))}
            </ButtonGroup>

            <Box sx={{ display: "flex", gap: 1 }}>
              <ButtonGroup
                size="small"
                sx={{
                  boxShadow: "none",
                  "& .MuiButton-root": {
                    borderColor: "divider",
                    color: "text.secondary",
                  },
                }}
              >
                <Button
                  onClick={handlePrevDay}
                  disabled={selectedDayIndex === 0}
                  sx={{ "&:hover": { bgcolor: "action.hover" } }}
                >
                  <ChevronLeftIcon fontSize="small" />
                </Button>
                <Button
                  onClick={handleNextDay}
                  disabled={selectedDayIndex === dayLabels.length - 1}
                  sx={{ "&:hover": { bgcolor: "action.hover" } }}
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
        sx={{
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
                  sx={{
                    mb: 1,
                    overflow: "hidden",
                    borderLeft: "6px solid",
                    borderLeftColor: alertColors[region.alert],
                    boxShadow: !!region.alert ? 1 : 0,
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
