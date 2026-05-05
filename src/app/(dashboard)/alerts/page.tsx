"use client";

import React, { useState } from "react";
import {
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Button,
  Pagination,
} from "@mui/material";
import MainCard from "@/ui-component/cards/MainCard";
import IconAlertCircle from "@mui/icons-material/ErrorOutline";
import SendIcon from "@mui/icons-material/Send";
import DoneAllIcon from "@mui/icons-material/DoneAll";
import { dummyAlerts } from "@/data/alerts";

export default function AlertsPage() {
  const [alerts, setAlerts] = useState(dummyAlerts);

  const getLevelColor = (level: string) => {
    switch (level) {
      case "red":
        return "error";
      case "orange":
        return "warning";
      case "yellow":
        return "info";
      default:
        return "default";
    }
  };

  const handleBroadcast = (id: string) => {
    setAlerts((prevAlerts) =>
      prevAlerts.map((alert) =>
        alert.id === id
          ? {
              ...alert,
              status: "dispatched",
              sentTo: Math.floor(Math.random() * 5000) + 1000,
            }
          : alert,
      ),
    );
  };

  return (
    <MainCard
      title="Gestion des Alertes"
      secondary={
        <Button
          variant="contained"
          color="primary"
          startIcon={<IconAlertCircle />}
          fullWidth
          sx={{ mt: { xs: 2, sm: 0 }, minHeight: 40 }}
        >
          Nouvelle Alerte Manuelle
        </Button>
      }
    >
      <Box sx={{ mb: 3 }}>
        <Typography variant="body2" color="text.secondary">
          Consultez, gérez et diffusez les recommandations/alertes aux résidents
          des régions ciblées.
        </Typography>
      </Box>

      <TableContainer
        component={Paper}
        elevation={0}
        sx={{ border: "1px solid", borderColor: "divider" }}
      >
        <Table sx={{ minWidth: 650 }}>
          <TableHead sx={{ bgcolor: "grey.50" }}>
            <TableRow>
              <TableCell sx={{ fontWeight: 600 }}>ID Alerte</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Région</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Date prévue</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Gravité</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Statut</TableCell>
              <TableCell align="right" sx={{ fontWeight: 600 }}>
                Actions
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {alerts.map((row) => (
              <TableRow key={row.id} hover>
                <TableCell>{row.id}</TableCell>
                <TableCell>{row.region}</TableCell>
                <TableCell>
                  {new Date(row.date).toLocaleString("fr-FR")}
                </TableCell>
                <TableCell>
                  <Chip
                    label={row.level.toUpperCase()}
                    color={getLevelColor(row.level) as any}
                    size="small"
                  />
                </TableCell>
                <TableCell>
                  {row.status === "dispatched" ? (
                    <Typography
                      variant="body2"
                      color="success.main"
                      sx={{ display: "flex", alignItems: "center", gap: 0.5 }}
                    >
                      <DoneAllIcon fontSize="small" /> Diffusé ({row.sentTo}{" "}
                      citoyens)
                    </Typography>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      En attente de diffusion
                    </Typography>
                  )}
                </TableCell>
                <TableCell align="right">
                  <Button
                    variant={
                      row.status === "pending" ? "contained" : "outlined"
                    }
                    color={row.level === "red" ? "error" : "primary"}
                    size="small"
                    startIcon={
                      row.status === "pending" ? <SendIcon /> : <DoneAllIcon />
                    }
                    disabled={row.status === "dispatched"}
                    onClick={() => handleBroadcast(row.id)}
                  >
                    {row.status === "pending"
                      ? "DIFFUSER SMS/EMAIL"
                      : "DIFFUSÉ"}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Box sx={{ mt: 3, display: "flex", justifyContent: "flex-end" }}>
        <Pagination count={1} color="primary" />
      </Box>
    </MainCard>
  );
}
