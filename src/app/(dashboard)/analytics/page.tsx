"use client";

import React, { useState } from "react";
import {
  Grid,
  Typography,
  Card,
  CardContent,
  Box,
  useTheme,
} from "@mui/material";
import dynamic from "next/dynamic";
import MainCard from "@/ui-component/cards/MainCard";

// ApexCharts is mostly client-side only. Next.js App Router needs SSR disabled for Apex.
const ReactApexChart = dynamic(() => import("react-apexcharts"), {
  ssr: false,
});

export default function AnalyticsPage() {
  const theme = useTheme();

  const tempTrendData = {
    options: {
      chart: {
        id: "heat-trends",
        toolbar: { show: false },
        fontFamily: `inherit`,
      },
      colors: [theme.palette.error.main, theme.palette.warning.main],
      dataLabels: { enabled: false },
      stroke: { curve: "smooth" as const, width: 3 },
      xaxis: {
        categories: [
          "Juin",
          "Juillet",
          "Aout",
          "Septembre",
          "Octobre",
          "Novembre",
          "Decembre",
          "Janvier",
          "Fevrier",
        ],
        labels: { style: { colors: theme.palette.text.secondary } },
      },
      yaxis: {
        labels: { style: { colors: theme.palette.text.secondary } },
      },
      grid: { borderColor: theme.palette.divider },
      tooltip: { theme: "light" },
      legend: { position: "top" as const, horizontalAlign: "right" as const },
    },
    series: [
      {
        name: "Max Marrakech (°C)",
        data: [42, 47, 48, 40, 35, 28, 22, 20, 25],
      },
      { name: "Max Tanger (°C)", data: [33, 35, 36, 31, 28, 22, 18, 16, 18] },
    ],
  };

  const incidentsData = {
    options: {
      chart: {
        type: "bar",
        toolbar: { show: false },
        fontFamily: `inherit`,
      },
      colors: [theme.palette.primary.main],
      plotOptions: {
        bar: { borderRadius: 4, horizontal: false, columnWidth: "50%" },
      },
      dataLabels: { enabled: false },
      xaxis: {
        categories: ["Sud", "Nord", "Oriental", "Centre"],
        labels: { style: { colors: theme.palette.text.secondary } },
      },
      grid: { borderColor: theme.palette.divider },
      tooltip: { theme: "light" },
    },
    series: [{ name: "Alertes Diffusées", data: [45, 12, 20, 34] }],
  };

  return (
    <MainCard title="Historique & Statistiques">
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Analyse rétrospective des tendances climatiques et des alertes canicule.
      </Typography>

      <Grid container spacing={3}>
        {/* Ligne 1 - KPIs */}
        <Grid size={{ xs: 12, sm: 4 }}>
          <Card
            sx={{
              bgcolor: "error.light",
              color: "error.dark",
              boxShadow: "none",
            }}
          >
            <CardContent>
              <Typography variant="h3" color="inherit">
                24
              </Typography>
              <Typography variant="subtitle2">
                Jours d'alertes extrêmes en 2024
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Card
            sx={{
              bgcolor: "warning.light",
              color: "warning.dark",
              boxShadow: "none",
            }}
          >
            <CardContent>
              <Typography variant="h3" color="inherit">
                +1.5°C
              </Typography>
              <Typography variant="subtitle2">
                Anomalie thermique moyenne
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Card
            sx={{
              bgcolor: "info.light",
              color: "info.dark",
              boxShadow: "none",
            }}
          >
            <CardContent>
              <Typography variant="h3" color="inherit">
                89%
              </Typography>
              <Typography variant="subtitle2">
                Taux de réception SMS (Citoyens)
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Ligne 2 - Graphique Températures */}
        <Grid size={{ xs: 12, md: 8 }}>
          <Card variant="outlined" sx={{ borderColor: "divider" }}>
            <CardContent>
              <Typography sx={{ mb: 2 }} variant="h6">
                Évolution des Températures Maximales
              </Typography>
              <Box sx={{ height: 300 }}>
                <ReactApexChart
                  options={tempTrendData.options}
                  series={tempTrendData.series}
                  type="line"
                  height={300}
                />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Ligne 2 - Graphique Alertes Réparties */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Card variant="outlined" sx={{ borderColor: "divider" }}>
            <CardContent>
              <Typography sx={{ mb: 2 }} variant="h6">
                Répartition Régionale
              </Typography>
              <Box sx={{ height: 300 }}>
                <ReactApexChart
                  options={incidentsData.options as any}
                  series={incidentsData.series}
                  type="bar"
                  height={300}
                />
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </MainCard>
  );
}
