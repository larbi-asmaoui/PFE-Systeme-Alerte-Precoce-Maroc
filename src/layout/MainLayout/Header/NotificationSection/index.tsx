import { useEffect, useRef, useState, ReactNode, RefObject } from "react";
import Link from "next/link";

// material-ui
import { useTheme } from "@mui/material/styles";
import {
  Avatar,
  Box,
  Button,
  CardActions,
  Chip,
  ClickAwayListener,
  Divider,
  Paper,
  Popper,
  Stack,
  TextField,
  Typography,
  useMediaQuery,
} from "@mui/material";

// project imports
import MainCard from "@/ui-component/cards/MainCard";
import Transitions from "@/ui-component/extended/Transitions";
import NotificationList from "./NotificationList";

// assets
import { IconBell } from "@tabler/icons-react";

// notification status options
const status = [
  {
    value: "all",
    label: "All Notification",
  },
  {
    value: "new",
    label: "New",
  },
  {
    value: "unread",
    label: "Unread",
  },
  {
    value: "other",
    label: "Other",
  },
];

// Activity wrapper for animation
const Activity = ({
  children,
  mode,
}: {
  children: ReactNode;
  mode: "visible" | "hidden";
}) => {
  // This wrapper mimics the original 'Activity' styled component if it had animation logic.
  // For now, it just renders children or could be replaced by Box with transitions if needed.
  // The original code imported 'Activity' from react? No, line 1 of original: `import { Activity, ... } from 'react';`
  // Wait, Activity is NOT a React export. It must have been a typo in original or a custom import they aliased?
  // Looking at the original imports:
  // `import { Activity, useEffect, useRef, useState } from 'react';`
  // `Activity` is NOT in React. This is strange. Maybe it was `import Activity from ...` but merged?
  // Or maybe it was `import { Activity } from 'react-feather'`? No, icon imports are tabler.
  // In the original file provided:
  // `import { Activity, ... } from 'react';` -> This line looks suspicious.
  // Let's assume it was a variable or component defined elsewhere or a mistake.
  // Actually, checking standard React exports, Activity is not one.
  // I will mock it as a simple Box for now.
  return (
    <Box sx={{ display: mode === "visible" ? "block" : "none" }}>
      {children}
    </Box>
  );
};

// ==============================|| NOTIFICATION ||============================== //

export default function NotificationSection() {
  const theme = useTheme();
  // @ts-ignore
  const downMD = useMediaQuery(theme.breakpoints.down("md"));

  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");

  /**
   * anchorRef is used on different components and specifying one type leads to other components throwing an error
   * */
  const anchorRef = useRef<any>(null);

  const handleToggle = () => {
    setOpen((prevOpen) => !prevOpen);
  };

  const handleClose = (event: MouseEvent | TouchEvent) => {
    if (anchorRef.current && anchorRef.current.contains(event.target as Node)) {
      return;
    }
    setOpen(false);
  };

  const prevOpen = useRef(open);
  useEffect(() => {
    if (prevOpen.current === true && open === false) {
      anchorRef.current?.focus();
    }
    prevOpen.current = open;
  }, [open]);

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setValue(event.target.value);
  };

  return (
    <>
      <Box sx={{ ml: 2 }}>
        <Avatar
          variant="rounded"
          sx={{
            ...theme.typography.commonAvatar,
            ...theme.typography.mediumAvatar,
            transition: "all .2s ease-in-out",
            color: theme.palette.warning.dark,
            background: theme.palette.warning.light,
            '&:hover, &[aria-controls="menu-list-grow"]': {
              color: theme.palette.warning.light,
              background: theme.palette.warning.dark,
            },
          }}
          ref={anchorRef}
          aria-controls={open ? "menu-list-grow" : undefined}
          aria-haspopup="true"
          onClick={handleToggle}
        >
          <IconBell stroke={1.5} size={20} />
        </Avatar>
      </Box>
      <Popper
        placement={downMD ? "bottom" : "bottom-end"}
        open={open}
        anchorEl={anchorRef.current}
        role={undefined}
        transition
        disablePortal
        modifiers={[
          { name: "offset", options: { offset: [downMD ? 5 : 0, 20] } },
        ]}
      >
        {({ TransitionProps }) => (
          <ClickAwayListener onClickAway={handleClose}>
            <Transitions
              position={downMD ? "top" : "top-right"}
              in={open}
              {...TransitionProps}
            >
              <Paper>
                {/** Use Box instead of Activity if component is missing */}
                <MainCard
                  border={false}
                  content={false}
                  boxShadow
                  shadow={theme.shadows[16]}
                  sx={{ maxWidth: 330 }}
                >
                  <Stack spacing={2}>
                    <Stack
                      direction="row"
                      alignItems="center"
                      justifyContent="space-between"
                      sx={{ pt: 2, px: 2 }}
                    >
                      <Stack direction="row" spacing={2}>
                        <Typography variant="subtitle1">
                          All Notification
                        </Typography>
                        <Chip
                          size="small"
                          label="01"
                          variant="filled"
                          sx={{
                            color: "background.default",
                            bgcolor: "warning.dark",
                          }}
                        />
                      </Stack>
                      <Typography
                        component={Link}
                        href="#"
                        variant="subtitle2"
                        sx={{ color: "primary.main", textDecoration: "none" }}
                      >
                        Mark as all read
                      </Typography>
                    </Stack>
                    <Box
                      sx={{
                        height: 1,
                        maxHeight: "calc(100vh - 205px)",
                        overflowX: "hidden",
                        "&::-webkit-scrollbar": { width: 5 },
                      }}
                    >
                      <Box sx={{ px: 2, pt: 0.25 }}>
                        <TextField
                          id="outlined-select-currency-native"
                          select
                          fullWidth
                          value={value}
                          onChange={handleChange}
                          SelectProps={{ native: true }}
                        >
                          {status.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </TextField>
                      </Box>
                      <Divider sx={{ mt: 2 }} />
                      <NotificationList />
                    </Box>
                  </Stack>
                  <CardActions sx={{ p: 1.25, justifyContent: "center" }}>
                    <Button size="small" disableElevation>
                      View All
                    </Button>
                  </CardActions>
                </MainCard>
              </Paper>
            </Transitions>
          </ClickAwayListener>
        )}
      </Popper>
    </>
  );
}
