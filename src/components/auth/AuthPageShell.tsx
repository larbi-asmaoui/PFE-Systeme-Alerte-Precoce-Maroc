/**
 * AuthPageShell – shared card layout for login & register pages.
 *
 * Handles the centered card, logo, title, subtitle, and footer link.
 * The actual form is passed as children — separation of layout vs logic.
 */

"use client";

import React from "react";
import {
  Box,
  Container,
  Divider,
  Grid,
  Paper,
  Typography,
  useTheme,
} from "@mui/material";
import Link from "next/link";
import Logo from "@/ui-component/Logo";

interface AuthPageShellProps {
  title: string;
  subtitle: string;
  footerText: string;
  footerLinkText: string;
  footerLinkHref: string;
  children: React.ReactNode;
}

export default function AuthPageShell({
  title,
  subtitle,
  footerText,
  footerLinkText,
  footerLinkHref,
  children,
}: AuthPageShellProps) {
  const theme = useTheme();

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        bgcolor: theme.palette.mode === "dark" ? "grey.900" : "grey.100",
        p: 2,
      }}
    >
      <Container maxWidth="xs">
        <Paper
          elevation={3}
          sx={{
            p: 4,
            display: "flex",
            flexDirection: "column",
            borderRadius: 3,
          }}
        >
          {/*  Header  */}
          <Box sx={{ mb: 3, textAlign: "center" }}>
            <Box sx={{ display: "flex", justifyContent: "center", mb: 2 }}>
              <Logo />
            </Box>
            <Typography variant="h4" fontWeight={700} gutterBottom>
              {title}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {subtitle}
            </Typography>
          </Box>

          <Divider sx={{ mb: 3 }} />

          {/*  Form (injected)  */}
          {children}

          {/*  Footer  */}
          <Divider sx={{ my: 3 }} />

          <Grid container justifyContent="center">
            <Grid>
              <Typography variant="body2" component="span">
                {footerText}{" "}
              </Typography>
              <Link
                href={footerLinkHref}
                passHref
                style={{ textDecoration: "none" }}
              >
                <Typography
                  variant="subtitle2"
                  color="secondary"
                  component="span"
                  sx={{ fontWeight: 600, cursor: "pointer" }}
                >
                  {footerLinkText}
                </Typography>
              </Link>
            </Grid>
          </Grid>
        </Paper>
      </Container>
    </Box>
  );
}
