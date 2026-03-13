import { useState, useEffect, useRef } from "react";
import { usePathname } from "next/navigation";

// material-ui
import { useTheme } from "@mui/material/styles";
import {
  ClickAwayListener,
  Collapse,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Paper,
  Popper,
  Typography,
  Tooltip,
} from "@mui/material";

// project imports
import NavItem from "../NavItem";
import { MenuItem } from "@/menu-items";
import { useConfig } from "@/contexts/ConfigContext";

// assets
import { IconChevronDown, IconChevronUp } from "@tabler/icons-react";
import FiberManualRecordIcon from "@mui/icons-material/FiberManualRecord";

interface NavCollapseProps {
  menu: MenuItem;
  level: number;
  drawerOpen: boolean;
}

export default function NavCollapse({
  menu,
  level,
  drawerOpen,
}: NavCollapseProps) {
  const theme = useTheme();
  const pathname = usePathname();
  const { config } = useConfig();
  const { borderRadius } = config;

  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const handleClick = () => {
    if (drawerOpen || level !== 1) {
      setOpen(!open);
      setSelected(!selected ? menu.id : null);
    }
  };

  const handleMouseEnter = (
    event:
      | React.MouseEvent<HTMLDivElement>
      | React.MouseEvent<HTMLAnchorElement>,
  ) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    if (!drawerOpen && level === 1) {
      setAnchorEl(event.currentTarget as HTMLElement);
    }
  };

  const handleMouseLeave = () => {
    timeoutRef.current = setTimeout(() => {
      setAnchorEl(null);
    }, 300); // Increased timeout to prevent accidental closes
  };

  const handlePopperMouseEnter = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
  };

  const handleClosePopper = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setAnchorEl(null);
  };

  const checkOpenForParent = (children: MenuItem[], id: string) => {
    children.forEach((item) => {
      if (item.url === pathname) {
        setOpen(true);
        setSelected(menu.id);
      }
      if (item.children) {
        checkOpenForParent(item.children, id);
      }
    });
  };

  useEffect(() => {
    setOpen(false);
    setSelected(null);
    setAnchorEl(null);
    if (menu.children) {
      checkOpenForParent(menu.children, menu.id);
    }
    // eslint-disable-next-line
  }, [pathname, menu.children]);

  const menus = menu.children?.map((item) => {
    switch (item.type) {
      case "collapse":
        return (
          <NavCollapse
            key={item.id}
            menu={item}
            level={level + 1}
            drawerOpen={drawerOpen}
          />
        );
      case "item":
        return (
          <NavItem
            key={item.id}
            item={item}
            level={level + 1}
            drawerOpen={drawerOpen}
          />
        );
      default:
        return (
          <Typography key={item.id} variant="h6" color="error" align="center">
            Menu Items Error
          </Typography>
        );
    }
  });

  const Icon = menu.icon;
  const menuIcon = menu.icon ? (
    <Icon
      strokeWidth={1.5}
      size="1.3rem"
      style={{ marginTop: "auto", marginBottom: "auto" }}
    />
  ) : (
    <FiberManualRecordIcon
      sx={{
        width: selected === menu.id ? 8 : 6,
        height: selected === menu.id ? 8 : 6,
      }}
      fontSize={level > 0 ? "inherit" : "medium"}
    />
  );

  return (
    <>
      <ListItemButton
        sx={{
          borderRadius: `${borderRadius}px`,
          mb: 0.5,
          alignItems: "flex-start",
          backgroundColor: level > 1 ? "transparent !important" : "inherit",
          py: level > 1 ? 1 : 1.25,
          pl: drawerOpen
            ? `${level * 24}px`
            : level === 1
              ? 1.25
              : `${16 + (level - 2) * 16}px`,
        }}
        selected={selected === menu.id || Boolean(anchorEl)}
        onClick={handleClick}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        <ListItemIcon
          sx={{
            my: "auto",
            minWidth: !menu.icon ? 18 : 36,
            color: selected === menu.id ? "secondary.main" : "text.primary",
            ...(!drawerOpen &&
              level === 1 && {
                borderRadius: `${borderRadius}px`,
                width: 46,
                height: 46,
                alignItems: "center",
                justifyContent: "center",
                mr: "auto",
                mb: 0,
                ...(selected === menu.id && {
                  bgcolor: "secondary.light",
                  color: "secondary.dark",
                }),
                "&:hover": {
                  bgcolor: "secondary.light",
                  color: "secondary.dark",
                },
              }),
          }}
        >
          {menuIcon}
        </ListItemIcon>
        {(drawerOpen || (!drawerOpen && level !== 1)) && (
          <Tooltip title={menu.title || ""} disableHoverListener={drawerOpen}>
            <ListItemText
              primary={
                <Typography
                  variant={selected === menu.id ? "h5" : "body1"}
                  color="inherit"
                  sx={{ my: "auto" }}
                >
                  {menu.title}
                </Typography>
              }
              secondary={
                menu.caption && (
                  <Typography
                    variant="caption"
                    sx={{ ...theme.typography.subMenuCaption }}
                    display="block"
                    gutterBottom
                  >
                    {menu.caption}
                  </Typography>
                )
              }
            />
          </Tooltip>
        )}
        {drawerOpen || level !== 1 ? (
          open ? (
            <IconChevronUp
              stroke={1.5}
              size="1rem"
              style={{ marginTop: "auto", marginBottom: "auto" }}
            />
          ) : (
            <IconChevronDown
              stroke={1.5}
              size="1rem"
              style={{ marginTop: "auto", marginBottom: "auto" }}
            />
          )
        ) : null}
      </ListItemButton>

      {/* For Drawer Open or Nested Levels */}
      {(drawerOpen || level !== 1) && (
        <Collapse in={open} timeout="auto" unmountOnExit>
          <List
            component="div"
            disablePadding
            sx={{
              position: "relative",
              "&:after": {
                content: "''",
                position: "absolute",
                left: "32px",
                top: 0,
                height: "100%",
                width: "1px",
                opacity: 1,
                background: theme.palette.primary.light,
              },
            }}
          >
            {menus}
          </List>
        </Collapse>
      )}

      {/* For Drawer Closed - Level 1 */}
      {!drawerOpen && level === 1 && (
        <Popper
          open={Boolean(anchorEl)}
          anchorEl={anchorEl}
          placement="right-start"
          style={{ zIndex: 2001 }}
          modifiers={[
            {
              name: "offset",
              options: {
                offset: [-12, 1],
              },
            },
          ]}
        >
          {({ TransitionProps }) => (
            <ClickAwayListener onClickAway={handleClosePopper}>
              <Paper
                elevation={16}
                onMouseEnter={handlePopperMouseEnter}
                onMouseLeave={handleMouseLeave}
                sx={{
                  borderRadius: `${borderRadius}px`,
                  minWidth: 150,
                  p: 0,
                  py: 1,
                  boxShadow: theme.shadows[8],
                }}
              >
                <List
                  component="div"
                  disablePadding
                  sx={{ position: "relative" }}
                >
                  {menus}
                </List>
              </Paper>
            </ClickAwayListener>
          )}
        </Popper>
      )}
    </>
  );
}
