"use client";

import React, { useState } from "react";
import {
  Box,
  Typography,
  Paper,
  Button,
  Slider,
  Grid,
  FormControlLabel,
  Switch,
  TextField,
  Divider,
} from "@mui/material";
import MainCard from "@/ui-component/cards/MainCard";
import SaveIcon from "@mui/icons-material/Save";

export default function SettingsPage() {
  const [thresholds, setThresholds] = useState([35, 42, 47]);
  const [autoSms, setAutoSms] = useState(false);

  const marks = [
    { value: 20, label: "20°C" },
    { value: 35, label: "Jaune" },
    { value: 42, label: "Orange" },
    { value: 47, label: "Rouge" },
    { value: 55, label: "55°C" },
  ];

  const handleSliderChange = (event: Event, newValue: number | number[]) => {
    setThresholds(newValue as number[]);
  };

  const handleSave = () => {
    // In a real app, this would dispatch an API call
    alert("Configuration sauvegardée avec succès !");
  };

  return (
    <MainCard
      title="Configuration Système"
      secondary={
        <Button
          variant="contained"
          startIcon={<SaveIcon />}
          onClick={handleSave}
          fullWidth
          sx={{ mt: { xs: 2, sm: 0 }, minHeight: 40 }}
        >
          Sauvegarder
        </Button>
      }
    >
      <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
        Définissez les règles métiers pour le déclenchement des alertes
        canicules automatiques et ajustez les seuils.
      </Typography>

      <Grid container spacing={4}>
        <Grid size={{ xs: 12, md: 7 }}>
          <Paper
            elevation={0}
            sx={{ p: 3, border: "1px solid", borderColor: "divider", mb: 3 }}
          >
            <Typography variant="h5" sx={{ mb: 1, color: "primary.main" }}>
              Seuils Climatiques de Référence
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
              Ces seuils déclenchent le changement de couleur et d'alerte sur la
              plateforme globale.
            </Typography>

            <Box sx={{ px: 2, pt: 4, pb: 2 }}>
              <Slider
                getAriaLabel={() => "Temperature range"}
                value={thresholds}
                onChange={handleSliderChange}
                valueLabelDisplay="on"
                getAriaValueText={(val) => `${val}°C`}
                step={1}
                marks={marks}
                min={20}
                max={55}
                disableSwap
                sx={{
                  color: "primary.main",
                  "& .MuiSlider-thumb": {
                    bgcolor: "white",
                    border: "2px solid currentColor",
                  },
                  "& .MuiSlider-track": {
                    background:
                      "linear-gradient(to right, #ffeb3b, #ed6c02, #d32f2f)",
                    border: "none",
                  },
                }}
              />
            </Box>

            <Box
              sx={{
                mt: 3,
                display: "flex",
                flexWrap: "wrap",
                gap: 2,
                justifyContent: "space-between",
                bgcolor: "grey.100",
                p: 2,
                borderRadius: 2,
              }}
            >
              <Box>
                <Typography variant="subtitle2" color="info.dark">
                  Jaune Modéré
                </Typography>
                <Typography variant="body2">
                  {">"} {thresholds[0]} °C
                </Typography>
              </Box>
              <Box>
                <Typography variant="subtitle2" color="warning.dark">
                  Orange Sévère
                </Typography>
                <Typography variant="body2">
                  {">"} {thresholds[1]} °C
                </Typography>
              </Box>
              <Box>
                <Typography variant="subtitle2" color="error.dark">
                  Rouge Extrême
                </Typography>
                <Typography variant="body2">
                  {">"} {thresholds[2]} °C
                </Typography>
              </Box>
            </Box>
          </Paper>
        </Grid>

        <Grid size={{ xs: 12, md: 5 }}>
          <Paper
            elevation={0}
            sx={{ p: 3, border: "1px solid", borderColor: "divider" }}
          >
            <Typography variant="h5" sx={{ mb: 2, color: "primary.main" }}>
              Conduite des Opérations
            </Typography>

            <FormControlLabel
              control={
                <Switch
                  checked={autoSms}
                  onChange={(e) => setAutoSms(e.target.checked)}
                  color="error"
                />
              }
              label={
                <Box>
                  <Typography variant="body1" sx={{ fontWeight: 600 }}>
                    Diffuser SMS Automatiquement
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Pour les alertes Rouges uniquement
                  </Typography>
                </Box>
              }
              sx={{ mb: 2 }}
            />
            <Divider sx={{ my: 2 }} />

            <Typography variant="subtitle2" sx={{ mb: 1 }}>
              Modèle SMS par Défaut (Urgence)
            </Typography>
            <TextField
              multiline
              rows={4}
              fullWidth
              variant="outlined"
              defaultValue={
                "⚠️ ALERTE CANICULE EXTRÊME | Région [REGION]. \nPrécautions : Restez à l'intérieur, hydratez-vous. Température: [TEMP]°C. \n- Protection Civile Maroc -"
              }
              InputProps={{
                sx: { fontSize: "0.875rem" },
              }}
            />
          </Paper>
        </Grid>
      </Grid>
    </MainCard>
  );
}
