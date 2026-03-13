import { useState, useRef, useEffect } from "react";
import { useTheme } from "@mui/material/styles";
import {
  Avatar,
  Box,
  Card,
  CardContent,
  Chip,
  ClickAwayListener,
  Divider,
  Grid,
  InputAdornment,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  OutlinedInput,
  Paper,
  Popper,
  Stack,
  Switch,
  Typography,
} from "@mui/material";

// third-party
// import PerfectScrollbar from 'react-perfect-scrollbar'; // Next.js might issue with this, using simple overflow for now

// project imports
// import MainCard from 'ui-component/cards/MainCard';
import Transitions from "@/ui-component/extended/Transitions";
import { useConfig } from "@/contexts/ConfigContext";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";

// assets
import {
  IconLogout,
  IconSearch,
  IconSettings,
  IconUser,
} from "@tabler/icons-react";

// ==============================|| PROFILE MENU ||============================== //

export default function ProfileSection() {
  const theme = useTheme();
  const router = useRouter();
  const { config } = useConfig();
  const { borderRadius } = config;
  const { user, logout } = useAuth();

  const [sdm, setSdm] = useState(true);
  const [value, setValue] = useState("");
  const [notification, setNotification] = useState(false);
  const [open, setOpen] = useState(false);

  /**
   * anchorRef is used on different components and specifying one type leads to other components throwing an error
   * */
  const anchorRef = useRef<any>(null);

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  const handleToggle = () => {
    setOpen((prevOpen) => !prevOpen);
  };

  const handleClose = (event: any) => {
    if (anchorRef.current && anchorRef.current.contains(event.target)) {
      return;
    }
    setOpen(false);
  };

  const prevOpen = useRef(open);
  useEffect(() => {
    if (prevOpen.current === true && open === false) {
      anchorRef.current.focus();
    }
    prevOpen.current = open;
  }, [open]);

  return (
    <>
      <Chip
        sx={{
          height: "48px",
          alignItems: "center",
          borderRadius: "27px",
          transition: "all .2s ease-in-out",
          borderColor: theme.palette.primary.light,
          backgroundColor: theme.palette.primary.light,
          '&[aria-controls="menu-list-grow"], &:hover': {
            borderColor: theme.palette.primary.main,
            background: `${theme.palette.primary.main} !important`,
            color: theme.palette.primary.light,
            "& svg": {
              stroke: theme.palette.primary.light,
            },
          },
          "& .MuiChip-label": {
            lineHeight: 0,
          },
        }}
        icon={
          <Avatar
            src="/assets/images/users/user-round.svg"
            sx={{
              ...theme.typography.mediumAvatar,
              margin: "8px 0 8px 8px !important",
              cursor: "pointer",
              background:
                "linear-gradient(135deg, rgb(23, 62, 67) 50%, rgb(63, 176, 172) 50%)",
              color: theme.palette.background.paper,
            }}
            ref={anchorRef}
            aria-controls={open ? "menu-list-grow" : undefined}
            aria-haspopup="true"
            color="inherit"
          />
        }
        label={
          <IconSettings
            stroke={1.5}
            size="1.5rem"
            color={theme.palette.primary.main}
          />
        }
        variant="outlined"
        ref={anchorRef}
        aria-controls={open ? "menu-list-grow" : undefined}
        aria-haspopup="true"
        onClick={handleToggle}
        color="primary"
      />
      <Popper
        placement="bottom-end"
        open={open}
        anchorEl={anchorRef.current}
        role={undefined}
        transition
        disablePortal
        popperOptions={{
          modifiers: [
            {
              name: "offset",
              options: {
                offset: [0, 14],
              },
            },
          ],
        }}
      >
        {({ TransitionProps }) => (
          <ClickAwayListener onClickAway={handleClose}>
            <Transitions in={open} {...TransitionProps}>
              <Paper>
                <Box sx={{ p: 2, pb: 0 }}>
                  <Stack>
                    <Stack direction="row" spacing={0.5} alignItems="center">
                      <Typography variant="h4">Good Morning,</Typography>
                      <Typography
                        component="span"
                        variant="h4"
                        sx={{ fontWeight: 400 }}
                      >
                        {user ? `${user.first_name} ${user.last_name}` : "User"}
                      </Typography>
                    </Stack>
                    <Typography variant="subtitle2">Project Admin</Typography>
                  </Stack>
                  <Divider sx={{ my: 2 }} />
                </Box>
                <Box sx={{ p: 2, pt: 0 }}>
                  <List
                    component="nav"
                    sx={{
                      width: "100%",
                      maxWidth: 350,
                      minWidth: 300,
                      backgroundColor: theme.palette.background.paper,
                      borderRadius: "10px",
                      [theme.breakpoints.down("md")]: {
                        minWidth: "100%",
                      },
                      "& .MuiListItemButton-root": {
                        mt: 0.5,
                      },
                    }}
                  >
                    <ListItemButton sx={{ borderRadius: `${borderRadius}px` }}>
                      <ListItemIcon>
                        <IconSettings stroke={1.5} size="1.3rem" />
                      </ListItemIcon>
                      <ListItemText
                        primary={
                          <Typography variant="body2">
                            Account Settings
                          </Typography>
                        }
                      />
                    </ListItemButton>
                    <ListItemButton
                      sx={{ borderRadius: `${borderRadius}px` }}
                      onClick={handleLogout}
                    >
                      <ListItemIcon>
                        <IconLogout stroke={1.5} size="1.3rem" />
                      </ListItemIcon>
                      <ListItemText
                        primary={
                          <Typography variant="body2">Logout</Typography>
                        }
                      />
                    </ListItemButton>
                  </List>
                </Box>
              </Paper>
            </Transitions>
          </ClickAwayListener>
        )}
      </Popper>
    </>
  );
}
