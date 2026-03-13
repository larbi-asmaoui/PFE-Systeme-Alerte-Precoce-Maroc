import React, { useState } from "react";

// material-ui
import { useTheme } from "@mui/material/styles";
import {
  Avatar,
  Box,
  Button,
  CardActions,
  CardContent,
  Divider,
  Grid,
  IconButton,
  Menu,
  MenuItem,
  Stack,
  Typography,
} from "@mui/material";

// project imports
import BajajAreaChartCard from "./BajajAreaChartCard";
import MainCard from "@/ui-component/cards/MainCard";
import SkeletonPopularCard from "@/ui-component/cards/Skeleton/PopularCard";
import { gridSpacing } from "@/store/constant";

// assets
import ChevronRightOutlinedIcon from "@mui/icons-material/ChevronRightOutlined";
import MoreHorizOutlinedIcon from "@mui/icons-material/MoreHorizOutlined";
import KeyboardArrowUpOutlinedIcon from "@mui/icons-material/KeyboardArrowUpOutlined";
import KeyboardArrowDownOutlinedIcon from "@mui/icons-material/KeyboardArrowDownOutlined";

interface PopularCardProps {
  isLoading?: boolean;
}

const PopularCard = ({ isLoading }: PopularCardProps) => {
  const theme = useTheme();

  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  return (
    <>
      {isLoading ? (
        <SkeletonPopularCard />
      ) : (
        <MainCard content={false}>
          <CardContent>
            <Stack spacing={gridSpacing}>
              <Stack
                direction="row"
                alignItems="center"
                justifyContent="space-between"
              >
                <Typography variant="h4">Popular Stocks</Typography>
                <IconButton
                  size="small"
                  sx={{ mt: -0.625 }}
                  aria-controls="menu-popular-card"
                  aria-haspopup="true"
                  onClick={handleClick}
                >
                  <MoreHorizOutlinedIcon
                    fontSize="small"
                    sx={{ cursor: "pointer" }}
                  />
                </IconButton>
              </Stack>
              <Menu
                id="menu-popular-card"
                anchorEl={anchorEl}
                keepMounted
                open={Boolean(anchorEl)}
                onClose={handleClose}
                variant="selectedMenu"
                anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
                transformOrigin={{ vertical: "top", horizontal: "right" }}
              >
                <MenuItem onClick={handleClose}> Today</MenuItem>
                <MenuItem onClick={handleClose}> This Month</MenuItem>
                <MenuItem onClick={handleClose}> This Year </MenuItem>
              </Menu>

              <BajajAreaChartCard />
              <Box>
                <Stack
                  direction="row"
                  alignItems="center"
                  justifyContent="space-between"
                >
                  <Typography variant="subtitle1" sx={{ color: "inherit" }}>
                    Bajaj Finery
                  </Typography>
                  <Stack direction="row" alignItems="center">
                    <Typography variant="subtitle1" sx={{ color: "inherit" }}>
                      $1839.00
                    </Typography>
                    <Avatar
                      variant="rounded"
                      sx={{
                        width: 16,
                        height: 16,
                        borderRadius: "5px",
                        bgcolor: "success.light",
                        color: "success.dark",
                        ml: 2,
                      }}
                    >
                      <KeyboardArrowUpOutlinedIcon
                        fontSize="small"
                        color="inherit"
                      />
                    </Avatar>
                  </Stack>
                </Stack>
                <Typography variant="subtitle2" sx={{ color: "success.dark" }}>
                  10% Profit
                </Typography>
                <Divider sx={{ my: 1.5 }} />
                <Stack
                  direction="row"
                  alignItems="center"
                  justifyContent="space-between"
                >
                  <Typography variant="subtitle1" sx={{ color: "inherit" }}>
                    TTML
                  </Typography>
                  <Stack direction="row" alignItems="center">
                    <Typography variant="subtitle1" sx={{ color: "inherit" }}>
                      $100.00
                    </Typography>
                    <Avatar
                      variant="rounded"
                      sx={{
                        width: 16,
                        height: 16,
                        borderRadius: "5px",
                        bgcolor: "orange.light",
                        color: "orange.dark",
                        marginLeft: 1.875,
                      }}
                    >
                      <KeyboardArrowDownOutlinedIcon
                        fontSize="small"
                        color="inherit"
                      />
                    </Avatar>
                  </Stack>
                </Stack>
                <Typography variant="subtitle2" sx={{ color: "orange.dark" }}>
                  10% loss
                </Typography>
                <Divider sx={{ my: 1.5 }} />
                <Stack
                  direction="row"
                  alignItems="center"
                  justifyContent="space-between"
                >
                  <Typography variant="subtitle1" sx={{ color: "inherit" }}>
                    Reliance
                  </Typography>
                  <Stack direction="row" alignItems="center">
                    <Typography variant="subtitle1" sx={{ color: "inherit" }}>
                      $200.00
                    </Typography>
                    <Avatar
                      variant="rounded"
                      sx={{
                        width: 16,
                        height: 16,
                        borderRadius: "5px",
                        bgcolor: "success.light",
                        color: "success.dark",
                        ml: 2,
                      }}
                    >
                      <KeyboardArrowUpOutlinedIcon
                        fontSize="small"
                        color="inherit"
                      />
                    </Avatar>
                  </Stack>
                </Stack>
                <Typography variant="subtitle2" sx={{ color: "success.dark" }}>
                  10% Profit
                </Typography>
                <Divider sx={{ my: 1.5 }} />
                <Stack
                  direction="row"
                  alignItems="center"
                  justifyContent="space-between"
                >
                  <Typography variant="subtitle1" sx={{ color: "inherit" }}>
                    TTML
                  </Typography>
                  <Stack direction="row" alignItems="center">
                    <Typography variant="subtitle1" sx={{ color: "inherit" }}>
                      $189.00
                    </Typography>
                    <Avatar
                      variant="rounded"
                      sx={{
                        width: 16,
                        height: 16,
                        borderRadius: "5px",
                        bgcolor: "orange.light",
                        color: "orange.dark",
                        ml: 2,
                      }}
                    >
                      <KeyboardArrowDownOutlinedIcon
                        fontSize="small"
                        color="inherit"
                      />
                    </Avatar>
                  </Stack>
                </Stack>
                <Typography variant="subtitle2" sx={{ color: "orange.dark" }}>
                  10% loss
                </Typography>
                <Divider sx={{ my: 1.5 }} />
                <Stack
                  direction="row"
                  alignItems="center"
                  justifyContent="space-between"
                >
                  <Typography variant="subtitle1" sx={{ color: "inherit" }}>
                    Stolon
                  </Typography>
                  <Stack direction="row" alignItems="center">
                    <Typography variant="subtitle1" sx={{ color: "inherit" }}>
                      $189.00
                    </Typography>
                    <Avatar
                      variant="rounded"
                      sx={{
                        width: 16,
                        height: 16,
                        borderRadius: "5px",
                        bgcolor: "orange.light",
                        color: "orange.dark",
                        ml: 2,
                      }}
                    >
                      <KeyboardArrowDownOutlinedIcon
                        fontSize="small"
                        color="inherit"
                      />
                    </Avatar>
                  </Stack>
                </Stack>
                <Typography variant="subtitle2" sx={{ color: "orange.dark" }}>
                  10% loss
                </Typography>
              </Box>
            </Stack>
          </CardContent>
          <CardActions sx={{ p: 1.25, pt: 0, justifyContent: "center" }}>
            <Button size="small" disableElevation>
              View All
              <ChevronRightOutlinedIcon />
            </Button>
          </CardActions>
        </MainCard>
      )}
    </>
  );
};

export default PopularCard;
