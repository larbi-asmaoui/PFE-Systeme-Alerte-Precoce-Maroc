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
  IconButton,
  Avatar,
} from "@mui/material";
import MainCard from "@/ui-component/cards/MainCard";
import PersonAddAlt1Icon from "@mui/icons-material/PersonAddAlt1";
import EditIcon from "@mui/icons-material/Edit";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import { dummyUsers } from "@/data/users";

export default function UsersPage() {
  const [users, setUsers] = useState(dummyUsers);

  const getStatusColor = (status: string) => {
    return status === "active" ? "success" : "default";
  };

  const getRoleChipColor = (role: string) => {
    if (role.toLowerCase().includes("admin")) return "primary";
    if (role.toLowerCase().includes("autorit")) return "secondary";
    return "default";
  };

  const stringAvatar = (name: string) => {
    return {
      children: `${name.split(" ")[0][0]}${name.split(" ")[1] ? name.split(" ")[1][0] : ""}`,
    };
  };

  return (
    <MainCard
      title="Annuaire & Utilisateurs"
      secondary={
        <Button
          variant="contained"
          color="secondary"
          startIcon={<PersonAddAlt1Icon />}
          fullWidth
          sx={{ mt: { xs: 2, sm: 0 }, minHeight: 40 }}
        >
          Ajouter Un Contact
        </Button>
      }
    >
      <Box sx={{ mb: 3 }}>
        <Typography variant="body2" color="text.secondary">
          Gestion des administrateurs régionaux et des listes de diffusion des
          citoyens inscrits pour recevoir des alertes par SMS/Email.
        </Typography>
      </Box>

      <TableContainer
        component={Paper}
        elevation={0}
        sx={{ border: "1px solid", borderColor: "divider" }}
      >
        <Table sx={{ minWidth: 700 }}>
          <TableHead sx={{ bgcolor: "grey.50" }}>
            <TableRow>
              <TableCell sx={{ fontWeight: 600 }}>Nom</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Rôle</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>
                Région d'affectation
              </TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Contact</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Statut</TableCell>
              <TableCell align="right" sx={{ fontWeight: 600 }}>
                Actions
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {users.map((row) => (
              <TableRow key={row.id} hover>
                <TableCell>
                  <Box sx={{ display: "flex", gap: 2, alignItems: "center" }}>
                    <Avatar
                      {...stringAvatar(row.name)}
                      sx={{ width: 32, height: 32, fontSize: "0.875rem" }}
                    />
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {row.name}
                    </Typography>
                  </Box>
                </TableCell>
                <TableCell>
                  <Chip
                    label={row.role}
                    color={getRoleChipColor(row.role) as any}
                    size="small"
                    variant="outlined"
                  />
                </TableCell>
                <TableCell>{row.region}</TableCell>
                <TableCell>
                  <Typography
                    variant="caption"
                    sx={{ display: "block", color: "text.secondary" }}
                  >
                    {row.email}
                  </Typography>
                  <Typography variant="caption" sx={{ display: "block" }}>
                    {row.phone}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Chip
                    label={row.status.toUpperCase()}
                    color={getStatusColor(row.status) as any}
                    size="small"
                  />
                </TableCell>
                <TableCell align="right">
                  <IconButton size="small" color="primary">
                    <EditIcon fontSize="small" />
                  </IconButton>
                  <IconButton size="small" color="error">
                    <DeleteOutlineIcon fontSize="small" />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </MainCard>
  );
}
