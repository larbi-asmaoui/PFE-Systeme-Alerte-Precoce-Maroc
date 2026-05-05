"use client";

import React, { useState } from "react";
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
} from "@mui/material";

// Icons
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import ExpandLess from "@mui/icons-material/ExpandLess";
import ExpandMore from "@mui/icons-material/ExpandMore";
import ThermostatIcon from "@mui/icons-material/Thermostat";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";

// --- DYNAMICALLY IMPORT MAP ---
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

// --- FAKE DATA ---
const fakeRegions = [
  {
    id: 1,
    name: "Marrakech-Safi",
    coords: [31.6295, -8.0363] as [number, number],
    alert: "red",
    temp: 47,
    message: "Vague de chaleur extrême. Danger de mort.",
  },
  {
    id: 2,
    name: "Souss-Massa",
    coords: [30.4278, -9.5981] as [number, number],
    alert: "red",
    temp: 46,
    message: "Alerte chaleur extrême. Restez à l'intérieur.",
  },
  {
    id: 3,
    name: "Fès-Meknès",
    coords: [34.0331, -5.0003] as [number, number],
    alert: "orange",
    temp: 42,
    message: "Forte chaleur. Évitez les activités en plein air.",
  },
  {
    id: 4,
    name: "Oriental",
    coords: [34.68, -1.91] as [number, number],
    alert: "orange",
    temp: 41,
    message: "Alerte de forte chaleur.",
  },
  {
    id: 5,
    name: "Casablanca-Settat",
    coords: [33.5731, -7.5898] as [number, number],
    alert: "yellow",
    temp: 35,
    message: "Chaleur modérée. Restez hydraté.",
  },
  {
    id: 6,
    name: "Rabat-Salé-Kénitra",
    coords: [34.0209, -6.8416] as [number, number],
    alert: "yellow",
    temp: 34,
    message: "Chaleur modérée.",
  },
  {
    id: 7,
    name: "Tanger-Tetouan-Al Hoceima",
    coords: [35.7595, -5.834] as [number, number],
    alert: "none",
    temp: 28,
    message: "Aucune alerte.",
  },
  {
    id: 8,
    name: "Drâa-Tafilalet",
    coords: [31.9314, -4.4243] as [number, number],
    alert: "orange",
    temp: 43,
    message: "Alerte de forte chaleur.",
  },
];

const alertColors: Record<string, string> = {
  red: "#d32f2f",
  orange: "#ed6c02",
  yellow: "#ffeb3b",
  none: "#e0e0e0",
};

const days = ["Maint.", "+24h", "Ven", "Sam", "Dim", "Lun", "Mar"];

export default function Dashboard() {
  const [expandedRegion, setExpandedRegion] = useState<number | null>(1);
  const [selectedDayIndex, setSelectedDayIndex] = useState<number>(0);

  const toggleRegion = (id: number) => {
    setExpandedRegion(expandedRegion === id ? null : id);
  };

  const handlePrevDay = () =>
    setSelectedDayIndex((prev) => Math.max(0, prev - 1));
  const handleNextDay = () =>
    setSelectedDayIndex((prev) => Math.min(days.length - 1, prev + 1));

  // Generates a fake date string
  const getFakeDateString = (index: number) => {
    const baseDate = new Date("2024-06-13T10:00:00Z");
    baseDate.setDate(baseDate.getDate() + index);

    const dayName = baseDate
      .toLocaleDateString("en-US", { weekday: "short" })
      .substring(0, 2);
    const dateStr = baseDate.toISOString().split("T")[0].replace(/-/g, ".");

    return `${dayName} ${dateStr} 10:00 - ${dayName} ${dateStr} 13:00 (GMT+1)`;
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
        {/* THE MAP */}
        <DynamicHeatMap regions={fakeRegions} />

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
          <Box
            sx={{
              width: 14,
              height: 14,
              borderRadius: "50%",
              bgcolor: alertColors.yellow,
            }}
            title="Modéré"
          />
          <Box
            sx={{
              width: 14,
              height: 14,
              borderRadius: "50%",
              bgcolor: alertColors.orange,
            }}
            title="Sévère"
          />
          <Box
            sx={{
              width: 14,
              height: 14,
              borderRadius: "50%",
              bgcolor: alertColors.red,
            }}
            title="Extrême"
          />
          <InfoOutlinedIcon
            sx={{
              fontSize: 16,
              color: "text.secondary",
              ml: 0.5,
              cursor: "pointer",
            }}
          />
        </Box>

        {/* FLOATING CONTROL: Forecast Time Scrubber */}
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
          {/* Top Date Tab */}
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
              borderBottom: "none",
            }}
          >
            <AccessTimeIcon fontSize="small" color="primary" />
            <Typography
              variant="body2"
              color="primary.main"
              sx={{ fontWeight: 600 }}
            >
              {getFakeDateString(selectedDayIndex)}
            </Typography>
          </Paper>

          {/* Main Scrubber Bar */}
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
            {/* Left: Days Buttons */}
            <ButtonGroup
              size="small"
              sx={{
                boxShadow: "none",
                "& .MuiButton-root": {
                  borderColor: "divider",
                  textTransform: "none",
                  px: 2,
                  fontWeight: 600,
                },
              }}
            >
              {days.map((day, index) => (
                <Button
                  key={day}
                  onClick={() => setSelectedDayIndex(index)}
                  sx={{
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
                  }}
                >
                  {day}
                </Button>
              ))}
            </ButtonGroup>

            {/* Right: Playback Controls */}
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
                  disabled={selectedDayIndex === days.length - 1}
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
          width: { xs: "100%", md: "400px" },
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
        <Box sx={{ p: 2, bgcolor: "primary.dark", color: "primary.light" }}>
          <Typography variant="h4" sx={{ color: "white" }}>
            Vague de Chaleur - Maroc
          </Typography>
          <Typography variant="subtitle2">
            Système National de Surveillance
          </Typography>
        </Box>

        <Box sx={{ p: 2, borderBottom: "1px solid", borderColor: "divider" }}>
          <FormControl fullWidth size="small" sx={{ mb: 2 }}>
            <InputLabel>Niveau d'Alerte</InputLabel>
            <Select label="Niveau d'Alerte" defaultValue="all">
              <MenuItem value="all">(Tous les Niveaux)</MenuItem>
              <MenuItem value="red">🔴 Alerte Extrême</MenuItem>
              <MenuItem value="orange">🟠 Alerte Sévère</MenuItem>
              <MenuItem value="yellow">🟡 Alerte Modérée</MenuItem>
              <MenuItem value="none">⚪ Aucune Alerte</MenuItem>
            </Select>
          </FormControl>
        </Box>

        <Box sx={{ flexGrow: 1, overflowY: "auto", p: 2, bgcolor: "grey.50" }}>
          <Typography
            variant="subtitle2"
            color="text.secondary"
            sx={{ mb: 1, ml: 1 }}
          >
            ALERTES RÉGIONALES
          </Typography>

          <List sx={{ p: 0 }}>
            {fakeRegions.map((region) => (
              <Card
                key={region.id}
                sx={{
                  mb: 1,
                  overflow: "hidden",
                  borderLeft: "6px solid",
                  borderLeftColor: alertColors[region.alert],
                  boxShadow: 1,
                }}
              >
                <ListItemButton
                  onClick={() => toggleRegion(region.id)}
                  sx={{ p: 1.5 }}
                >
                  <ListItemIcon sx={{ minWidth: 36 }}>
                    {region.alert !== "none" ? (
                      <WarningAmberIcon
                        sx={{ color: alertColors[region.alert] }}
                      />
                    ) : (
                      <InfoOutlinedIcon color="disabled" />
                    )}
                  </ListItemIcon>
                  <ListItemText
                    primary={region.name}
                    primaryTypographyProps={{
                      fontWeight: 600,
                      variant: "body2",
                    }}
                  />
                  {region.alert !== "none" && (
                    <Typography
                      variant="body2"
                      fontWeight="bold"
                      sx={{ color: alertColors[region.alert], mr: 2 }}
                    >
                      {region.temp}°C
                    </Typography>
                  )}
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
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        mb: 1,
                        color: "text.secondary",
                      }}
                    >
                      <ThermostatIcon fontSize="small" sx={{ mr: 0.5 }} />
                      <Typography variant="body2">
                        Temp. Max Prévue: <strong>{region.temp}°C</strong>
                      </Typography>
                    </Box>
                    <Typography variant="body2" color="text.secondary">
                      {region.message}
                    </Typography>
                  </Box>
                </Collapse>
              </Card>
            ))}
          </List>
        </Box>
      </Box>
    </Box>
  );
}
