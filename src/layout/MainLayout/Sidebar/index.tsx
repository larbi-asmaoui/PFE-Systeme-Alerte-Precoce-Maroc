"use client";

import { memo, useMemo } from "react";

import { useTheme, styled, Theme, CSSObject } from "@mui/material/styles";
import { Box, Drawer, useMediaQuery, Chip, Stack } from "@mui/material";

import MenuList from "../MenuList";
import LogoSection from "../LogoSection";
import { drawerWidth, miniDrawerWidth } from "@/store/constant";
import { useConfig } from "@/contexts/ConfigContext";

const openedMixin = (theme: Theme): CSSObject => ({
  width: drawerWidth,
  transition: theme.transitions.create("width", {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.enteringScreen,
  }),
  overflowX: "hidden",
});

const closedMixin = (theme: Theme): CSSObject => ({
  transition: theme.transitions.create("width", {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.leavingScreen,
  }),
  overflowX: "hidden",
  width: miniDrawerWidth,
  [theme.breakpoints.up("sm")]: {
    width: miniDrawerWidth,
  },
});

// Styled Drawer
const DrawerStyled = styled(Drawer, {
  shouldForwardProp: (prop) => prop !== "open",
})(({ theme, open }) => ({
  width: drawerWidth,
  flexShrink: 0,
  whiteSpace: "nowrap",
  boxSizing: "border-box",
  ...(open && {
    ...openedMixin(theme),
    "& .MuiDrawer-paper": openedMixin(theme),
  }),
  ...(!open && {
    ...closedMixin(theme),
    "& .MuiDrawer-paper": closedMixin(theme),
  }),
}));

interface SidebarProps {
  open: boolean;
  handleDrawerToggle: () => void;
}

function Sidebar({ open, handleDrawerToggle }: SidebarProps) {
  const theme = useTheme();
  const matchUpMd = useMediaQuery(theme.breakpoints.up("md"));
  const { config } = useConfig();
  const { borderRadius } = config;

  const drawerContent = (
    <>
      <Box sx={{ display: { xs: "block", md: "none" }, p: 3 }}>
        <LogoSection />
      </Box>
      <Box
        sx={{
          px: open ? 2 : 0,
          mt: open ? 0 : 2.5,
        }}
      >
        <MenuList drawerOpen={open} />
      </Box>
    </>
  );

  return (
    <Box
      component="nav"
      sx={{
        flexShrink: { md: 0 },
        width: matchUpMd ? drawerWidth : "auto",
      }}
      aria-label="mailbox folders"
    >
      <Drawer
        container={
          typeof window !== "undefined" ? window.document.body : undefined
        }
        variant="temporary"
        open={!matchUpMd && open}
        onClose={handleDrawerToggle}
        ModalProps={{ keepMounted: true, disableScrollLock: true }}
        sx={{
          display: { xs: "block", md: "none" },
          "& .MuiDrawer-paper": {
            width: drawerWidth,
            background: theme.palette.background.paper,
            color: theme.palette.text.primary,
            borderRight: "none",
          },
        }}
      >
        {drawerContent}
      </Drawer>
      <DrawerStyled
        variant="permanent"
        open={open}
        sx={{
          display: { xs: "none", md: "block" },
          "& .MuiDrawer-paper": {
            background: theme.palette.background.paper,
            color: theme.palette.text.primary,
            borderRight: "none",
            top: "88px",
          },
        }}
      >
        {drawerContent}
      </DrawerStyled>
    </Box>
  );
}

export default memo(Sidebar);
