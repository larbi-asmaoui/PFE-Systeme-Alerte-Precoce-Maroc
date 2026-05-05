"use client";

import { useEffect, useState, ReactNode } from "react";

// material-ui
import { useTheme } from "@mui/material/styles";
import { Box, Toolbar, AppBar, useMediaQuery } from "@mui/material";

// project imports
import Header from "./Header";
import Sidebar from "./Sidebar";
import MainContentStyled from "./MainContentStyled";
import { useConfig } from "@/contexts/ConfigContext";
import { drawerWidth } from "@/store/constant";

// assets
import { IconChevronRight } from "@tabler/icons-react";

interface MainLayoutProps {
  children: ReactNode;
}

// ==============================|| MAIN LAYOUT ||============================== //

export default function MainLayout({ children }: MainLayoutProps) {
  const theme = useTheme();
  const downMD = useMediaQuery(theme.breakpoints.down("md"));

  // Handle drawer state locally for now, replacing Redux
  const [drawerOpen, setDrawerOpen] = useState(true);

  const { config } = useConfig();
  const { borderRadius } = config;

  const handleDrawerToggle = () => {
    setDrawerOpen(!drawerOpen);
  };

  useEffect(() => {
    setDrawerOpen(!downMD);
  }, [downMD]);

  return (
    <Box sx={{ display: "flex" }}>
      {/* header */}
      <AppBar
        enableColorOnDark
        position="fixed"
        color="inherit"
        elevation={0}
        sx={{
          bgcolor: "background.default",
          transition: drawerOpen ? theme.transitions.create("width") : "none",
        }}
      >
        <Toolbar sx={{ p: 2 }}>
          <Header open={drawerOpen} handleDrawerToggle={handleDrawerToggle} />
        </Toolbar>
      </AppBar>

      {/* drawer */}
      <Sidebar open={drawerOpen} handleDrawerToggle={handleDrawerToggle} />

      {/* main content */}
      <MainContentStyled open={drawerOpen} borderRadius={borderRadius}>
        {/* breadcrumb */}
        {children}
      </MainContentStyled>

      {/* <Customization /> */}
    </Box>
  );
}
