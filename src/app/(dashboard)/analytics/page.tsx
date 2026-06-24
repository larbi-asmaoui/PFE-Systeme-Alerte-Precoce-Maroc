"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  Grid,
  Typography,
  Card,
  CardContent,
  Box,
  Skeleton,
  useTheme,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import WbSunnyIcon from "@mui/icons-material/WbSunny";
import LocalFireDepartmentIcon from "@mui/icons-material/LocalFireDepartment";
import BedtimeIcon from "@mui/icons-material/Bedtime";
import dynamic from "next/dynamic";
import type { ApexOptions } from "apexcharts";
import MainCard from "@/ui-component/cards/MainCard";

// ApexCharts is mostly client-side only. Next.js App Router needs SSR disabled for Apex.
const ReactApexChart = dynamic(() => import("react-apexcharts"), {
  ssr: false,
});

// ---------------------------------------------------------------------------
// Types (mirror scripts/compute_climate_stats.py output)
// ---------------------------------------------------------------------------
interface ClimateStats {
  generated_at: string;
  source: string;
  baseline_period: string;
  n_stations: number;
  year_range: [number, number];
  kpis: {
    warming_rate_c_per_decade: number | null;
    latest_year: number | null;
    latest_summer_anomaly_c: number | null;
    heatwave_days_latest: number | null;
    warm_nights_latest: number | null;
  };
  series: {
    years: number[];
    tmax_anomaly_c: (number | null)[];
    annual_mean_tmax_c: (number | null)[];
    summer_anomaly_c: (number | null)[];
    heatwave_days: number[];
    warm_nights: number[];
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const signed = (v: number | null | undefined, unit = "") =>
  v == null ? "—" : `${v > 0 ? "+" : ""}${v}${unit}`;

export default function AnalyticsPage() {
  const theme = useTheme();
  const [stats, setStats] = useState<ClimateStats | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch("/data/climate_stats.json")
      .then((r) => {
        if (!r.ok) throw new Error("not found");
        return r.json();
      })
      .then((d: ClimateStats) => setStats(d))
      .catch(() => setError(true));
  }, []);

  // ---- KPI card definitions ----
  const kpiCards = useMemo(() => {
    const k = stats?.kpis;
    return [
      {
        value: signed(k?.warming_rate_c_per_decade, "°C"),
        label: "Réchauffement par décennie (Tmax)",
        color: "#c62828",
        Icon: TrendingUpIcon,
      },
      {
        value: signed(k?.latest_summer_anomaly_c, "°C"),
        label: `Anomalie estivale ${k?.latest_year ?? ""} vs ${stats?.baseline_period ?? ""}`,
        color: "#ef6c00",
        Icon: WbSunnyIcon,
      },
      {
        value: k?.heatwave_days_latest ?? "—",
        label: `Jours de canicule en ${k?.latest_year ?? ""}`,
        color: "#e53935",
        Icon: LocalFireDepartmentIcon,
      },
      {
        value: k?.warm_nights_latest ?? "—",
        label: `Nuits chaudes en ${k?.latest_year ?? ""}`,
        color: "#3949ab",
        Icon: BedtimeIcon,
      },
    ];
  }, [stats]);

  // ---- Chart: summer anomaly (diverging bar) ----
  const anomalyChart = useMemo(() => {
    const years = stats?.series.years ?? [];
    const data = stats?.series.summer_anomaly_c ?? [];
    const options: ApexOptions = {
      chart: { type: "bar", toolbar: { show: false }, fontFamily: "inherit" },
      plotOptions: {
        bar: {
          borderRadius: 3,
          columnWidth: "70%",
          colors: {
            ranges: [
              { from: -100, to: 0, color: "#1e88e5" },
              { from: 0.0001, to: 100, color: theme.palette.error.main },
            ],
          },
        },
      },
      dataLabels: { enabled: false },
      xaxis: {
        categories: years,
        tickAmount: 8,
        labels: { style: { colors: theme.palette.text.secondary } },
      },
      yaxis: {
        labels: {
          formatter: (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}°`,
          style: { colors: theme.palette.text.secondary },
        },
      },
      grid: { borderColor: theme.palette.divider },
      tooltip: {
        theme: "light",
        y: { formatter: (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(2)} °C` },
      },
    };
    return { options, series: [{ name: "Anomalie estivale", data }] };
  }, [stats, theme]);

  // ---- Chart: heatwave days & warm nights ----
  const trendChart = useMemo(() => {
    const years = stats?.series.years ?? [];
    const options: ApexOptions = {
      chart: { type: "line", toolbar: { show: false }, fontFamily: "inherit" },
      colors: ["#e53935", "#fb8c00"],
      stroke: { curve: "smooth", width: 3 },
      dataLabels: { enabled: false },
      markers: { size: 0, hover: { size: 4 } },
      xaxis: {
        categories: years,
        tickAmount: 8,
        labels: { style: { colors: theme.palette.text.secondary } },
      },
      yaxis: {
        labels: {
          formatter: (v: number) => `${Math.round(v)} j`,
          style: { colors: theme.palette.text.secondary },
        },
      },
      grid: { borderColor: theme.palette.divider },
      tooltip: { theme: "light", y: { formatter: (v: number) => `${Math.round(v)} jours` } },
      legend: { position: "top", horizontalAlign: "right" },
    };
    return {
      options,
      series: [
        { name: "Jours de canicule", data: stats?.series.heatwave_days ?? [] },
        { name: "Nuits chaudes", data: stats?.series.warm_nights ?? [] },
      ],
    };
  }, [stats, theme]);

  const loading = !stats && !error;

  return (
    <MainCard title="Historique & Statistiques Climatiques">
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        {stats
          ? `Tendances long terme du changement climatique au Maroc — ${stats.source}, ${stats.n_stations} stations, ${stats.year_range[0]}–${stats.year_range[1]} (référence ${stats.baseline_period}).`
          : "Analyse rétrospective des tendances climatiques et des canicules."}
      </Typography>

      {error && (
        <Typography variant="body2" color="error" sx={{ mb: 2 }}>
          Données climatiques indisponibles. Exécutez{" "}
          <code>python scripts/compute_climate_stats.py</code> pour les générer.
        </Typography>
      )}

      <Grid container spacing={3}>
        {/* Ligne 1 - KPIs */}
        {kpiCards.map((c, i) => (
          <Grid key={i} size={{ xs: 12, sm: 6, md: 3 }}>
            <Card
              variant="outlined"
              sx={{
                height: "100%",
                borderColor: "divider",
                bgcolor: alpha(c.color, 0.06),
                boxShadow: "none",
              }}
            >
              <CardContent
                sx={{ display: "flex", alignItems: "center", gap: 1.5 }}
              >
                <Box
                  sx={{
                    width: 44,
                    height: 44,
                    flexShrink: 0,
                    borderRadius: 2,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    bgcolor: alpha(c.color, 0.14),
                    color: c.color,
                  }}
                >
                  <c.Icon fontSize="small" />
                </Box>
                <Box sx={{ minWidth: 0 }}>
                  {loading ? (
                    <Skeleton variant="text" width={70} height={36} />
                  ) : (
                    <Typography
                      variant="h3"
                      sx={{ color: c.color, lineHeight: 1.1, fontWeight: 700 }}
                    >
                      {c.value}
                    </Typography>
                  )}
                  <Typography variant="caption" color="text.secondary">
                    {c.label}
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}

        {/* Ligne 2 - Anomalie de température estivale */}
        <Grid size={{ xs: 12 }}>
          <Card variant="outlined" sx={{ borderColor: "divider" }}>
            <CardContent>
              <Typography variant="h6">Anomalie de Température Estivale (JJA)</Typography>
              <Typography variant="caption" color="text.secondary">
                Écart de la température maximale estivale par rapport à la normale{" "}
                {stats?.baseline_period ?? "1991-2020"}
              </Typography>
              <Box sx={{ height: 320, mt: 1 }}>
                {loading ? (
                  <Skeleton variant="rounded" height={320} />
                ) : (
                  <ReactApexChart
                    options={anomalyChart.options}
                    series={anomalyChart.series}
                    type="bar"
                    height={320}
                  />
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Ligne 3 - Jours de canicule & nuits chaudes */}
        <Grid size={{ xs: 12 }}>
          <Card variant="outlined" sx={{ borderColor: "divider" }}>
            <CardContent>
              <Typography variant="h6">Jours de Canicule & Nuits Chaudes par An</Typography>
              <Typography variant="caption" color="text.secondary">
                Nombre de jours dépassant le 90ᵉ percentile climatologique (moyenne nationale)
              </Typography>
              <Box sx={{ height: 320, mt: 1 }}>
                {loading ? (
                  <Skeleton variant="rounded" height={320} />
                ) : (
                  <ReactApexChart
                    options={trendChart.options}
                    series={trendChart.series}
                    type="line"
                    height={320}
                  />
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </MainCard>
  );
}
