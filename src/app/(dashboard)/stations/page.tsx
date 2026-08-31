"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  Grid,
  Typography,
  Box,
  Stack,
  Chip,
  Skeleton,
  MenuItem,
  TextField,
  useTheme,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import PlaceIcon from "@mui/icons-material/Place";
import TerrainIcon from "@mui/icons-material/Terrain";
import LocalFireDepartmentIcon from "@mui/icons-material/LocalFireDepartment";
import AcUnitIcon from "@mui/icons-material/AcUnit";
import EventIcon from "@mui/icons-material/Event";
import dynamic from "next/dynamic";
import type { ApexOptions } from "apexcharts";
import MainCard from "@/ui-component/cards/MainCard";

const ReactApexChart = dynamic(() => import("react-apexcharts"), {
  ssr: false,
});

// ---------------------------------------------------------------------------
// Types (mirror scripts/build_station_history.py output)
// ---------------------------------------------------------------------------
interface StationMeta {
  code: string;
  station_id: string;
  station_name: string;
  lat: number;
  lon: number;
  elevation: number;
  start: string;
  end: string;
  n_years: number;
  n_obs: number;
}
interface MonthlyPoint {
  month: string;
  tmax: number | null;
  tmin: number | null;
  heat_index: number | null;
  wind_chill: number | null;
}
interface AnnualPoint {
  year: number;
  tmax: number | null;
  heat_index: number | null;
  wind_chill: number | null;
}
interface RecentPoint {
  date: string;
  heat_index: number | null;
  wind_chill: number | null;
}
interface StationHistory {
  meta: StationMeta;
  monthly: MonthlyPoint[];
  annual: AnnualPoint[];
  records: {
    hottest: { value: number; date: string };
    coldest: { value: number; date: string };
  };
  recent: RecentPoint[];
}
interface HistoryPayload {
  n_stations: number;
  stations: StationHistory[];
}

const fmtDate = (iso: string) =>
  new Date(iso + "T12:00:00Z").toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

// ---------------------------------------------------------------------------
// KPI tile
// ---------------------------------------------------------------------------
function KpiTile({
  icon,
  label,
  value,
  sub,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
  color: string;
}) {
  return (
    <MainCard border={false} content={false} sx={{ height: "100%" }}>
      <Box sx={{ p: 2.25, display: "flex", gap: 1.5, alignItems: "center" }}>
        <Box
          sx={{
            width: 46,
            height: 46,
            borderRadius: 2,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color,
            bgcolor: alpha(color, 0.12),
            flexShrink: 0,
          }}
        >
          {icon}
        </Box>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h4" sx={{ fontWeight: 800, lineHeight: 1.1 }}>
            {value}
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ fontWeight: 600, display: "block" }}
          >
            {label}
          </Typography>
          {sub && (
            <Typography variant="caption" color="text.disabled" noWrap>
              {sub}
            </Typography>
          )}
        </Box>
      </Box>
    </MainCard>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function StationsHistoryPage() {
  const theme = useTheme();
  const [payload, setPayload] = useState<HistoryPayload | null>(null);
  const [error, setError] = useState(false);
  const [code, setCode] = useState<string>("");

  useEffect(() => {
    fetch("/data/stations_history.json")
      .then((r) => {
        if (!r.ok) throw new Error("not found");
        return r.json();
      })
      .then((d: HistoryPayload) => {
        setPayload(d);
        if (d.stations.length) setCode(d.stations[0].meta.code);
      })
      .catch(() => setError(true));
  }, []);

  const station = useMemo(
    () => payload?.stations.find((s) => s.meta.code === code) ?? null,
    [payload, code],
  );

  const heat = theme.palette.error.main;
  const cold = theme.palette.info.main;

  // ---- Monthly climatology (seasonal cycle) ----
  const monthlyChart = useMemo(() => {
    const cats = station?.monthly.map((m) => m.month) ?? [];
    const options: ApexOptions = {
      chart: { type: "line", toolbar: { show: false }, fontFamily: "inherit" },
      colors: [heat, cold],
      stroke: { curve: "smooth", width: 3 },
      dataLabels: { enabled: false },
      markers: { size: 0, hover: { size: 5 } },
      legend: { position: "top", horizontalAlign: "right" },
      xaxis: {
        categories: cats,
        labels: { style: { colors: theme.palette.text.secondary } },
      },
      yaxis: {
        labels: {
          formatter: (v: number) => `${v.toFixed(0)}°`,
          style: { colors: theme.palette.text.secondary },
        },
      },
      grid: { borderColor: theme.palette.divider },
      tooltip: {
        theme: "light",
        y: { formatter: (v: number) => `${v?.toFixed(1)} °C` },
      },
    };
    return {
      options,
      series: [
        {
          name: "Heat Index",
          data: station?.monthly.map((m) => m.heat_index) ?? [],
        },
        {
          name: "Wind Chill Index",
          data: station?.monthly.map((m) => m.wind_chill) ?? [],
        },
      ],
    };
  }, [station, theme, heat, cold]);

  // ---- Long-term annual trend ----
  const annualChart = useMemo(() => {
    const cats = station?.annual.map((a) => a.year) ?? [];
    const options: ApexOptions = {
      chart: { type: "line", toolbar: { show: false }, fontFamily: "inherit" },
      colors: [theme.palette.warning.main, heat],
      stroke: { curve: "straight", width: [2, 3] },
      dataLabels: { enabled: false },
      markers: { size: 0, hover: { size: 4 } },
      legend: { position: "top", horizontalAlign: "right" },
      xaxis: {
        categories: cats,
        tickAmount: 8,
        labels: { style: { colors: theme.palette.text.secondary } },
      },
      yaxis: {
        labels: {
          formatter: (v: number) => `${v.toFixed(0)}°`,
          style: { colors: theme.palette.text.secondary },
        },
      },
      grid: { borderColor: theme.palette.divider },
      tooltip: {
        theme: "light",
        y: { formatter: (v: number) => `${v?.toFixed(2)} °C` },
      },
    };
    return {
      options,
      series: [
        {
          name: "Tmax moyenne",
          data: station?.annual.map((a) => a.tmax) ?? [],
        },
        {
          name: "Heat Index moyen",
          data: station?.annual.map((a) => a.heat_index) ?? [],
        },
      ],
    };
  }, [station, theme, heat]);

  // ---- Recent 90-day conditions ----
  const recentChart = useMemo(() => {
    const cats = station?.recent.map((r) => r.date) ?? [];
    const options: ApexOptions = {
      chart: { type: "area", toolbar: { show: false }, fontFamily: "inherit" },
      colors: [heat, cold],
      stroke: { curve: "smooth", width: 2 },
      fill: {
        type: "gradient",
        gradient: { opacityFrom: 0.35, opacityTo: 0.02 },
      },
      dataLabels: { enabled: false },
      legend: { position: "top", horizontalAlign: "right" },
      xaxis: {
        categories: cats,
        type: "datetime",
        labels: { style: { colors: theme.palette.text.secondary } },
      },
      yaxis: {
        labels: {
          formatter: (v: number) => `${v.toFixed(0)}°`,
          style: { colors: theme.palette.text.secondary },
        },
      },
      grid: { borderColor: theme.palette.divider },
      tooltip: {
        theme: "light",
        x: { format: "dd MMM yyyy" },
        y: { formatter: (v: number) => `${v?.toFixed(1)} °C` },
      },
    };
    return {
      options,
      series: [
        {
          name: "Heat Index",
          data: station?.recent.map((r) => r.heat_index) ?? [],
        },
        {
          name: "Wind Chill Index",
          data: station?.recent.map((r) => r.wind_chill) ?? [],
        },
      ],
    };
  }, [station, theme, heat, cold]);

  if (error) {
    return (
      <MainCard title="Historique par Station">
        <Typography color="error">
          Données introuvables. Lancez{" "}
          <code>python scripts/build_station_history.py</code> pour générer{" "}
          <code>public/data/stations_history.json</code>.
        </Typography>
      </MainCard>
    );
  }

  return (
    <Grid container spacing={2.5}>
      {/* ---- Header + station picker ---- */}
      <Grid size={12}>
        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={2}
          alignItems={{ xs: "stretch", sm: "center" }}
          justifyContent="space-between"
        >
          <Box>
            <Typography variant="h3" sx={{ fontWeight: 800 }}>
              Historique par Station
            </Typography>
          </Box>
          {payload ? (
            <TextField
              select
              size="small"
              label="Station"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              sx={{ minWidth: 260 }}
            >
              {payload.stations.map((s) => (
                <MenuItem key={s.meta.code} value={s.meta.code}>
                  {s.meta.station_name}
                </MenuItem>
              ))}
            </TextField>
          ) : (
            <Skeleton variant="rounded" width={260} height={40} />
          )}
        </Stack>
      </Grid>

      {/* ---- KPI tiles ---- */}
      {!station ? (
        [0, 1, 2, 3].map((i) => (
          <Grid key={i} size={{ xs: 12, sm: 6, md: 3 }}>
            <Skeleton variant="rounded" height={92} />
          </Grid>
        ))
      ) : (
        <>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiTile
              icon={<PlaceIcon />}
              color={theme.palette.primary.main}
              value={`${station.meta.lat}°, ${station.meta.lon}°`}
              label="Coordonnées"
              sub={`${station.meta.n_years} ans · ${station.meta.n_obs.toLocaleString("fr-FR")} obs.`}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiTile
              icon={<TerrainIcon />}
              color={theme.palette.success.main}
              value={`${station.meta.elevation} m`}
              label="Altitude"
              sub={`${fmtDate(station.meta.start)} → ${fmtDate(station.meta.end)}`}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiTile
              icon={<LocalFireDepartmentIcon />}
              color={heat}
              value={`${station.records.hottest.value}°C`}
              label="Record de chaleur"
              sub={fmtDate(station.records.hottest.date)}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiTile
              icon={<AcUnitIcon />}
              color={cold}
              value={`${station.records.coldest.value}°C`}
              label="Record de froid"
              sub={fmtDate(station.records.coldest.date)}
            />
          </Grid>
        </>
      )}

      {/* ---- Seasonal cycle ---- */}
      <Grid size={{ xs: 12, md: 6 }}>
        <MainCard title="Cycle saisonnier (moyenne mensuelle)">
          {station ? (
            <ReactApexChart
              options={monthlyChart.options}
              series={monthlyChart.series}
              type="line"
              height={300}
            />
          ) : (
            <Skeleton variant="rounded" height={300} />
          )}
        </MainCard>
      </Grid>

      {/* ---- Long-term trend ---- */}
      <Grid size={{ xs: 12, md: 6 }}>
        <MainCard title="Tendance à long terme (moyenne annuelle)">
          {station ? (
            <ReactApexChart
              options={annualChart.options}
              series={annualChart.series}
              type="line"
              height={300}
            />
          ) : (
            <Skeleton variant="rounded" height={300} />
          )}
        </MainCard>
      </Grid>

      {/* ---- Recent conditions ---- */}
      <Grid size={12}>
        <MainCard
          title="Conditions récentes (90 derniers jours)"
          secondary={
            station ? (
              <Chip
                size="small"
                icon={<EventIcon />}
                label={`jusqu'au ${fmtDate(station.meta.end)}`}
                variant="outlined"
              />
            ) : undefined
          }
        >
          {station ? (
            <ReactApexChart
              options={recentChart.options}
              series={recentChart.series}
              type="area"
              height={320}
            />
          ) : (
            <Skeleton variant="rounded" height={320} />
          )}
        </MainCard>
      </Grid>
    </Grid>
  );
}
