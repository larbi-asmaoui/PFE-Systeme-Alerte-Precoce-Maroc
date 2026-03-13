import PropTypes from "prop-types";
import React, { useState } from "react";

// material-ui
import { useTheme } from "@mui/material/styles";
import {
  Avatar,
  Box,
  CardMedia,
  Menu,
  MenuItem,
  Stack,
  Typography,
} from "@mui/material";

// project imports
import MainCard from "@/ui-component/cards/MainCard";
import EarningCardSkeleton from "@/ui-component/cards/Skeleton/EarningCard";

// assets
import MoreHorizIcon from "@mui/icons-material/MoreHoriz";
import ArrowUpwardIcon from "@mui/icons-material/ArrowUpward";
import GetAppTwoToneIcon from "@mui/icons-material/GetAppOutlined";
import FileCopyTwoToneIcon from "@mui/icons-material/FileCopyOutlined";
import PictureAsPdfTwoToneIcon from "@mui/icons-material/PictureAsPdfOutlined";
import ArchiveTwoToneIcon from "@mui/icons-material/ArchiveOutlined";

interface EarningCardProps {
  isLoading?: boolean;
}

const EarningCard = ({ isLoading }: EarningCardProps) => {
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
        <EarningCardSkeleton />
      ) : (
        <MainCard
          border={false}
          content={false}
          sx={{
            bgcolor: "secondary.dark",
            color: "#fff",
            overflow: "hidden",
            position: "relative",
            "&:after": {
              content: '""',
              position: "absolute",
              width: 210,
              height: 210,
              background: theme.palette.secondary.main, // Use main or dark depending on look
              borderRadius: "50%",
              top: { xs: -85 },
              right: { xs: -95 },
            },
            "&:before": {
              content: '""',
              position: "absolute",
              width: 210,
              height: 210,
              background: theme.palette.secondary.main,
              borderRadius: "50%",
              top: { xs: -125 },
              right: { xs: -15 },
              opacity: 0.5,
            },
          }}
        >
          <Box sx={{ p: 2.25, position: "relative", zIndex: 1 }}>
            <Stack direction="row" justifyContent="space-between">
              <Avatar
                variant="rounded"
                sx={{
                  ...theme.typography.largeAvatar,
                  borderRadius: "8px",
                  bgcolor: "secondary.800",
                  mt: 1,
                }}
              >
                <img
                  src="/assets/images/icons/earning.svg"
                  alt="Notification"
                  style={{ width: 30, height: 30 }}
                />
              </Avatar>
              <Avatar
                variant="rounded"
                sx={{
                  ...theme.typography.commonAvatar,
                  ...theme.typography.mediumAvatar,
                  bgcolor: "secondary.dark",
                  color: "secondary.200",
                  zIndex: 1,
                }}
                aria-controls="menu-earning-card"
                aria-haspopup="true"
                onClick={handleClick}
              >
                <MoreHorizIcon fontSize="inherit" />
              </Avatar>
            </Stack>
            <Menu
              id="menu-earning-card"
              anchorEl={anchorEl}
              keepMounted
              open={Boolean(anchorEl)}
              onClose={handleClose}
              variant="selectedMenu"
              anchorOrigin={{
                vertical: "bottom",
                horizontal: "right",
              }}
              transformOrigin={{
                vertical: "top",
                horizontal: "right",
              }}
            >
              <MenuItem onClick={handleClose}>
                <GetAppTwoToneIcon sx={{ mr: 1.75 }} /> Import Card
              </MenuItem>
              <MenuItem onClick={handleClose}>
                <FileCopyTwoToneIcon sx={{ mr: 1.75 }} /> Copy Data
              </MenuItem>
              <MenuItem onClick={handleClose}>
                <PictureAsPdfTwoToneIcon sx={{ mr: 1.75 }} /> Export
              </MenuItem>
              <MenuItem onClick={handleClose}>
                <ArchiveTwoToneIcon sx={{ mr: 1.75 }} /> Archive File
              </MenuItem>
            </Menu>
            <Stack direction="row" alignItems="center">
              <Typography
                sx={{
                  fontSize: "2.125rem",
                  fontWeight: 500,
                  mr: 1,
                  mt: 1.75,
                  mb: 0.75,
                  color: "#fff", // Explicit white color
                  position: "relative", // Ensure z-index applies
                  zIndex: 2,
                }}
              >
                $500.00
              </Typography>
              <Avatar
                sx={{
                  ...theme.typography.smallAvatar,
                  bgcolor: "secondary.200",
                  color: "secondary.dark",
                }}
              >
                <ArrowUpwardIcon
                  fontSize="inherit"
                  sx={{ transform: "rotate3d(1, 1, 1, 45deg)" }}
                />
              </Avatar>
            </Stack>
            <Typography
              sx={{
                mb: 1.25,
                fontSize: "1rem",
                fontWeight: 500,
                color: "secondary.light", // Ensures visibility on dark background
              }}
            >
              Total Earning
            </Typography>
          </Box>
        </MainCard>
      )}
    </>
  );
};

export default EarningCard;
