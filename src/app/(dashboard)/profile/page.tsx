"use client";

import React, { useState } from "react";
import {
  Box,
  Typography,
  Grid,
  TextField,
  Button,
  Paper,
  Avatar,
  Divider,
  Switch,
  FormControlLabel,
  InputAdornment,
  IconButton,
} from "@mui/material";
import MainCard from "@/ui-component/cards/MainCard";

// Icons
import SaveIcon from "@mui/icons-material/Save";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import VpnKeyIcon from "@mui/icons-material/VpnKey";
import NotificationsActiveIcon from "@mui/icons-material/NotificationsActive";
import PersonIcon from "@mui/icons-material/Person";

export default function ProfilePage() {
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [formData, setFormData] = useState({
    firstName: "Admin",
    lastName: "National",
    email: "admin@sap.ma",
    phone: "+212 600-000000",
    role: "Administrateur National",
  });

  const [settings, setSettings] = useState({
    emailAlerts: true,
    smsAlerts: false,
    weeklyReport: true,
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSettingChange =
    (name: string) => (e: React.ChangeEvent<HTMLInputElement>) => {
      setSettings({ ...settings, [name]: e.target.checked });
    };

  const handleSaveProfile = () => {
    alert("Profil mis à jour avec succès");
  };

  const handleSaveSecurity = () => {
    alert("Mot de passe mis à jour");
  };

  return (
    <MainCard title="Paramètres du Compte">
      <Box sx={{ mb: 3 }}>
        <Typography variant="body2" color="text.secondary">
          Gérez vos informations personnelles, vos préférences de sécurité et
          vos notifications.
        </Typography>
      </Box>

      <Grid container spacing={4}>
        {/* ======================= COLUMN 1: PROFILE INFO ======================= */}
        <Grid size={{ xs: 12, md: 7 }}>
          <Paper
            elevation={0}
            sx={{ p: 3, border: "1px solid", borderColor: "divider", mb: 3 }}
          >
            <Box sx={{ display: "flex", alignItems: "center", gap: 3, mb: 4 }}>
              <Avatar
                sx={{
                  width: 80,
                  height: 80,
                  bgcolor: "primary.main",
                  fontSize: "2rem",
                }}
              >
                {formData.firstName.charAt(0)}
                {formData.lastName.charAt(0)}
              </Avatar>
              <Box>
                <Typography variant="h4" sx={{ mb: 0.5 }}>
                  {formData.firstName} {formData.lastName}
                </Typography>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mb: 1 }}
                >
                  {formData.role}
                </Typography>
                <Button variant="outlined" size="small">
                  Changer la photo
                </Button>
              </Box>
            </Box>

            <Divider sx={{ my: 3 }} />

            <Typography
              variant="h5"
              sx={{ mb: 3, display: "flex", alignItems: "center", gap: 1 }}
            >
              <PersonIcon fontSize="small" /> Informations Personnelles
            </Typography>

            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  fullWidth
                  label="Prénom"
                  name="firstName"
                  value={formData.firstName}
                  onChange={handleChange}
                  variant="outlined"
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  fullWidth
                  label="Nom de famille"
                  name="lastName"
                  value={formData.lastName}
                  onChange={handleChange}
                  variant="outlined"
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  fullWidth
                  label="Adresse Email"
                  name="email"
                  type="email"
                  value={formData.email}
                  onChange={handleChange}
                  variant="outlined"
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  fullWidth
                  label="Numéro de Téléphone"
                  name="phone"
                  value={formData.phone}
                  onChange={handleChange}
                  variant="outlined"
                />
              </Grid>
            </Grid>

            <Box sx={{ mt: 3, display: "flex", justifyContent: "flex-end" }}>
              <Button
                variant="contained"
                onClick={handleSaveProfile}
                startIcon={<SaveIcon />}
                fullWidth
                sx={{
                  mt: { xs: 2, sm: 0 },
                  minHeight: 40,
                  width: { xs: "100%", sm: "auto" },
                }}
              >
                Mettre à jour le profil
              </Button>
            </Box>
          </Paper>

          {/* ======================= PREFERENCES SECTION ======================= */}
          <Paper
            elevation={0}
            sx={{ p: 3, border: "1px solid", borderColor: "divider" }}
          >
            <Typography
              variant="h5"
              sx={{ mb: 3, display: "flex", alignItems: "center", gap: 1 }}
            >
              <NotificationsActiveIcon fontSize="small" /> Préférences de
              Notification
            </Typography>

            <FormControlLabel
              control={
                <Switch
                  checked={settings.emailAlerts}
                  onChange={handleSettingChange("emailAlerts")}
                  color="primary"
                />
              }
              label="Recevoir les alertes d'urgence par Email"
              sx={{ display: "flex", mb: 1 }}
            />
            <FormControlLabel
              control={
                <Switch
                  checked={settings.smsAlerts}
                  onChange={handleSettingChange("smsAlerts")}
                  color="primary"
                />
              }
              label="Recevoir les alertes d'urgence par SMS"
              sx={{ display: "flex", mb: 1 }}
            />
            <FormControlLabel
              control={
                <Switch
                  checked={settings.weeklyReport}
                  onChange={handleSettingChange("weeklyReport")}
                  color="primary"
                />
              }
              label="Envoyer un rapport hebdomadaire des incidents"
              sx={{ display: "flex", mb: 1 }}
            />
          </Paper>
        </Grid>

        {/* ======================= COLUMN 2: SECURITY ======================= */}
        <Grid size={{ xs: 12, md: 5 }}>
          <Paper
            elevation={0}
            sx={{ p: 3, border: "1px solid", borderColor: "divider" }}
          >
            <Typography
              variant="h5"
              sx={{
                mb: 3,
                display: "flex",
                alignItems: "center",
                gap: 1,
                color: "error.main",
              }}
            >
              <VpnKeyIcon fontSize="small" /> Sécurité du Compte
            </Typography>

            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Veuillez utiliser un mot de passe fort contenant des lettres, des
              chiffres et des caractères spéciaux.
            </Typography>

            <TextField
              fullWidth
              label="Mot de passe actuel"
              type="password"
              variant="outlined"
              sx={{ mb: 2 }}
            />

            <Divider sx={{ my: 3 }} />

            <TextField
              fullWidth
              label="Nouveau mot de passe"
              type={showPassword ? "text" : "password"}
              variant="outlined"
              sx={{ mb: 2 }}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowPassword(!showPassword)}
                      edge="end"
                    >
                      {showPassword ? (
                        <VisibilityIcon />
                      ) : (
                        <VisibilityOffIcon />
                      )}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />

            <TextField
              fullWidth
              label="Confirmer le nouveau mot de passe"
              type={showConfirmPassword ? "text" : "password"}
              variant="outlined"
              sx={{ mb: 3 }}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() =>
                        setShowConfirmPassword(!showConfirmPassword)
                      }
                      edge="end"
                    >
                      {showConfirmPassword ? (
                        <VisibilityIcon />
                      ) : (
                        <VisibilityOffIcon />
                      )}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />

            <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
              <Button
                variant="contained"
                color="error"
                onClick={handleSaveSecurity}
                fullWidth
                sx={{ minHeight: 40, width: { xs: "100%", sm: "auto" } }}
              >
                Changer le mot de passe
              </Button>
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </MainCard>
  );
}
