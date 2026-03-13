import { useState } from "react";

// material-ui
import { useTheme } from "@mui/material/styles";
import { Avatar, Box, Button, Grid, Stack, Typography } from "@mui/material";

// third-party - Charts are dynamically imported in Next.js usually, but we have a wrapper or can use dynamic import here if needed.
// However, since this is a client component (will be used in page.tsx which is client), we can use the wrapper.
import Chart from "@/ui-component/charts/Chart";

// project imports
import MainCard from "@/ui-component/cards/MainCard";
import TotalOrderCardSkeleton from "@/ui-component/cards/Skeleton/EarningCard"; // Uses same skeleton structure
import chartOptions from "@/ui-component/chart-data/total-order-line-chart";

// assets
import LocalMallOutlinedIcon from "@mui/icons-material/LocalMallOutlined";
import ArrowDownwardIcon from "@mui/icons-material/ArrowDownward";

interface TotalOrderLineChartCardProps {
  isLoading?: boolean;
}

// data
const monthlyData = [{ data: [45, 66, 41, 89, 25, 44, 9, 54] }];
const yearlyData = [{ data: [35, 44, 9, 54, 45, 66, 41, 69] }];

const TotalOrderLineChartCard = ({
  isLoading,
}: TotalOrderLineChartCardProps) => {
  const theme = useTheme();

  const [timeValue, setTimeValue] = useState(false);
  const [series, setSeries] = useState(yearlyData);

  const handleChangeTime = (
    _event: React.MouseEvent<HTMLButtonElement>,
    newValue: boolean,
  ) => {
    setTimeValue(newValue);
    if (newValue) {
      setSeries(monthlyData);
    } else {
      setSeries(yearlyData);
    }
  };

  return (
    <>
      {isLoading ? (
        <TotalOrderCardSkeleton />
      ) : (
        <MainCard
          border={false}
          content={false}
          sx={{
            bgcolor: "primary.dark",
            color: "#fff",
            overflow: "hidden",
            position: "relative",
            "&>div": {
              position: "relative",
              zIndex: 5,
            },
            "&:after": {
              content: '""',
              position: "absolute",
              width: 210,
              height: 210,
              background: theme.palette.primary.main,
              borderRadius: "50%",
              top: { xs: -85 },
              right: { xs: -95 },
            },
            "&:before": {
              content: '""',
              position: "absolute",
              width: 210,
              height: 210,
              background: theme.palette.primary.main,
              borderRadius: "50%",
              top: { xs: -125 },
              right: { xs: -15 },
              opacity: 0.5,
            },
          }}
        >
          <Box sx={{ p: 2.25 }}>
            <Stack direction="row" justifyContent="space-between">
              <Avatar
                variant="rounded"
                sx={{
                  ...theme.typography.largeAvatar,
                  borderRadius: "8px",
                  bgcolor: "primary.800",
                  color: "common.white",
                  mt: 1,
                }}
              >
                <LocalMallOutlinedIcon fontSize="inherit" />
              </Avatar>
              <Box>
                <Button
                  disableElevation
                  variant={timeValue ? "contained" : "text"}
                  size="small"
                  sx={{ color: "inherit" }}
                  onClick={(e) => handleChangeTime(e, true)}
                >
                  Month
                </Button>
                <Button
                  disableElevation
                  variant={!timeValue ? "contained" : "text"}
                  size="small"
                  sx={{ color: "inherit" }}
                  onClick={(e) => handleChangeTime(e, false)}
                >
                  Year
                </Button>
              </Box>
            </Stack>

            <Grid container sx={{ mb: 0.75 }}>
              <Grid size={6}>
                <Box>
                  <Stack direction="row" alignItems="center">
                    <Typography
                      sx={{
                        fontSize: "2.125rem",
                        fontWeight: 500,
                        mr: 1,
                        mt: 1.75,
                        mb: 0.75,
                      }}
                    >
                      {timeValue ? "$108" : "$961"}
                    </Typography>
                    <Avatar
                      sx={{
                        ...theme.typography.smallAvatar,
                        bgcolor: "primary.200",
                        color: "primary.dark",
                      }}
                    >
                      <ArrowDownwardIcon
                        fontSize="inherit"
                        sx={{ transform: "rotate3d(1, 1, 1, 45deg)" }}
                      />
                    </Avatar>
                  </Stack>
                  <Typography
                    sx={{
                      fontSize: "1rem",
                      fontWeight: 500,
                      color: "primary.200",
                    }}
                  >
                    Total Order
                  </Typography>
                </Box>
              </Grid>
              <Grid size={6}>
                {/* Width handling for charts might need adjustment in Grid */}
                <Box
                  sx={{
                    ".apexcharts-tooltip.apexcharts-theme-light": {
                      color: theme.palette.text.primary,
                      background: theme.palette.background.default,
                    },
                  }}
                >
                  <Chart
                    options={chartOptions}
                    series={series}
                    type="line"
                    height={90}
                  />
                </Box>
              </Grid>
            </Grid>
          </Box>
        </MainCard>
      )}
    </>
  );
};

export default TotalOrderLineChartCard;
