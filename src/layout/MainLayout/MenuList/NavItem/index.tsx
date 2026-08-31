import { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

// material-ui
import { useTheme, alpha } from "@mui/material/styles";
import {
  Avatar,
  Chip,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
  useMediaQuery,
  Tooltip,
} from "@mui/material";

// project imports
import { MenuItem } from "@/menu-items";
import { useConfig } from "@/contexts/ConfigContext";

// assets
import FiberManualRecordIcon from "@mui/icons-material/FiberManualRecord";

interface NavItemProps {
  item: MenuItem;
  level: number;
  drawerOpen: boolean;
}

export default function NavItem({ item, level, drawerOpen }: NavItemProps) {
  const theme = useTheme();
  const pathname = usePathname();
  const { config } = useConfig();
  const { borderRadius } = config;
  const matchesSM = useMediaQuery(theme.breakpoints.down("lg"));

  // Active state logic
  const isSelected = pathname === item.url;

  const Icon = item?.icon;
  const itemIcon = item?.icon ? (
    <Icon stroke={1.5} size="1.3rem" />
  ) : (
    <FiberManualRecordIcon
      sx={{
        width: isSelected ? 8 : 6,
        height: isSelected ? 8 : 6,
      }}
      fontSize={level > 0 ? "inherit" : "medium"}
    />
  );

  let itemTarget = "_self";
  if (item.target) {
    itemTarget = "_blank";
  }

  let listItemProps = {
    component: Link,
    href: item.url!,
    target: itemTarget,
  };

  if (item?.external) {
    // @ts-ignore
    listItemProps = { component: "a", href: item.url, target: itemTarget };
  }

  // Need to implement custom state handling for drawer open/close if needed
  // For now using simple logic

  return (
    <ListItemButton
      {...listItemProps}
      disabled={item.disabled}
      sx={{
        borderRadius: `${borderRadius}px`,
        mb: 0.5,
        position: "relative",
        overflow: "hidden",
        backgroundColor: level > 1 ? "transparent !important" : "inherit",
        py: level > 1 ? 1 : 1.25,
        transition: theme.transitions.create(["background-color", "color", "transform"], {
          duration: theme.transitions.duration.shorter,
        }),
        ...(drawerOpen && level !== 1 && { ml: `${level * 18}px` }),
        ...(!drawerOpen && level === 1 && { pl: 1.25 }), // Match Vite's 10px padding
        ...(!drawerOpen && level !== 1 && { pl: `${16 + (level - 2) * 16}px` }),
        // Idle-item hover for open, top-level items: subtle tint + nudge.
        ...(drawerOpen &&
          level === 1 &&
          !isSelected && {
            "&:hover": {
              backgroundColor: `${theme.palette.secondary.light} !important`,
              transform: "translateX(3px)",
              "& .MuiListItemIcon-root": { color: theme.palette.secondary.main },
            },
          }),
        ...((!drawerOpen || level !== 1) && {
          py: level === 1 ? 0 : 1,
          "&:hover": {
            bgcolor: "transparent",
          },
          "&.Mui-selected": {
            "&:hover": {
              bgcolor: "transparent",
            },
            bgcolor: "transparent",
          },
        }),
        ...(drawerOpen &&
          level === 1 &&
          isSelected && {
            color: `${theme.palette.secondary.dark} !important`,
            background: `linear-gradient(90deg, ${theme.palette.secondary.light} 0%, ${alpha(
              theme.palette.secondary.light,
              0.35,
            )} 100%) !important`,
            fontWeight: 700,
            // Left accent bar marking the active route.
            "&::before": {
              content: '""',
              position: "absolute",
              left: 0,
              top: 6,
              bottom: 6,
              width: 4,
              borderRadius: 4,
              backgroundColor: theme.palette.secondary.main,
            },
            "& .MuiListItemIcon-root": {
              color: `${theme.palette.secondary.main} !important`,
            },
            "&:hover": {
              color: `${theme.palette.secondary.dark} !important`,
              background: `linear-gradient(90deg, ${theme.palette.secondary.light} 0%, ${alpha(
                theme.palette.secondary.light,
                0.35,
              )} 100%) !important`,
              "& .MuiListItemIcon-root": {
                color: `${theme.palette.secondary.main} !important`,
              },
            },
          }),
      }}
      selected={isSelected}
    >
      <ListItemIcon
        sx={{
          my: "auto",
          minWidth: !item?.icon ? 18 : 36,
          color: isSelected ? "secondary.main" : "text.primary",
          ...(!drawerOpen &&
            level === 1 && {
              borderRadius: `${borderRadius}px`,
              width: 46,
              height: 46,
              alignItems: "center",
              justifyContent: "center",
              mr: "auto",
              mb: 0,
              "&:hover": {
                bgcolor: "secondary.light",
                color: "secondary.dark",
              },
              ...(isSelected && {
                bgcolor: "secondary.light",
                color: "secondary.dark",
                "&:hover": {
                  bgcolor: "secondary.light",
                  color: "secondary.dark",
                },
              }),
            }),
        }}
      >
        {itemIcon}
      </ListItemIcon>
      {(drawerOpen || (!drawerOpen && level !== 1)) && (
        <Tooltip title={item.title || ""} disableHoverListener={drawerOpen}>
          <ListItemText
            primary={
              <Typography variant={isSelected ? "h5" : "body1"} color="inherit">
                {item.title}
              </Typography>
            }
            secondary={
              item.caption && (
                <Typography
                  variant="caption"
                  sx={{ ...theme.typography.subMenuCaption }}
                  display="block"
                  gutterBottom
                >
                  {item.caption}
                </Typography>
              )
            }
          />
        </Tooltip>
      )}
      {drawerOpen && item.chip && (
        <Chip
          color={item.chip.color}
          variant={item.chip.variant}
          size={item.chip.size}
          label={item.chip.label}
          avatar={item.chip.avatar && <Avatar>{item.chip.avatar}</Avatar>}
        />
      )}
    </ListItemButton>
  );
}
