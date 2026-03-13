import { useEffect, useState } from "react";

// material-ui
import { useTheme } from "@mui/material/styles";
import { Box, MenuItem, Stack, TextField, Typography } from "@mui/material";

// third-party
import Chart from "@/ui-component/charts/Chart";

// project imports
import MainCard from "@/ui-component/cards/MainCard";
import SkeletonTotalGrowthBarChart from "@/ui-component/cards/Skeleton/TotalGrowthBarChart";
import { gridSpacing } from "@/store/constant";
import { useConfig } from "@/contexts/ConfigContext";

// chart data
import chartData from "@/ui-component/chart-data/total-growth-bar-chart";

const status = [
  { value: "today", label: "Today" },
  { value: "month", label: "This Month" },
  { value: "year", label: "This Year" },
];

interface TotalGrowthBarChartProps {
  isLoading?: boolean;
}

const series = [
  {
    name: "Investment",
    data: [35, 125, 35, 35, 35, 80, 35, 20, 35, 45, 15, 75],
  },
  { name: "Loss", data: [35, 15, 15, 35, 65, 40, 80, 25, 15, 85, 25, 75] },
  { name: "Profit", data: [35, 145, 35, 35, 20, 105, 100, 10, 65, 45, 30, 10] },
  { name: "Maintenance", data: [0, 0, 75, 0, 0, 115, 0, 0, 0, 0, 150, 0] },
];

const TotalGrowthBarChart = ({ isLoading }: TotalGrowthBarChartProps) => {
  const theme = useTheme();
  // @ts-ignore
  const { config } = useConfig();
  const { fontFamily } = config;

  const [value, setValue] = useState("today");
  const [chartOptions, setChartOptions] = useState(chartData);

  const textPrimary = theme.palette.text.primary;
  const divider = theme.palette.divider;
  const grey500 = theme.palette.grey[500];

  const primary200 = theme.palette.primary[200];
  const primaryDark = theme.palette.primary.dark;
  const secondaryMain = theme.palette.secondary.main;
  const secondaryLight = theme.palette.secondary.light;

  useEffect(() => {
    setChartOptions((prevState) => ({
      ...prevState,
      chart: { ...prevState.chart, fontFamily: fontFamily },
      colors: [primary200, primaryDark, secondaryMain, secondaryLight],
      xaxis: {
        ...prevState.xaxis,
        labels: {
          style: {
            colors: [
              textPrimary,
              textPrimary,
              textPrimary,
              textPrimary,
              textPrimary,
              textPrimary,
              textPrimary,
              textPrimary,
              textPrimary,
              textPrimary,
              textPrimary,
              textPrimary,
            ],
          },
        },
      },
      yaxis: {
        ...prevState.yaxis,
        labels: { style: { colors: [textPrimary] } },
      },
      grid: { borderColor: divider },
      tooltip: { theme: "light" },
      legend: { ...prevState.legend, labels: { colors: grey500 } },
    }));
  }, [
    fontFamily,
    primary200,
    primaryDark,
    secondaryMain,
    secondaryLight,
    textPrimary,
    grey500,
    divider,
  ]);

  return (
    <>
      {isLoading ? (
        <SkeletonTotalGrowthBarChart />
      ) : (
        <MainCard>
          <Stack spacing={gridSpacing}>
            <Stack
              direction="row"
              alignItems="center"
              justifyContent="space-between"
            >
              <Stack spacing={1}>
                <Typography variant="subtitle2">Total Growth</Typography>
                <Typography variant="h3">$2,324.00</Typography>
              </Stack>
              <TextField
                id="standard-select-currency"
                select
                value={value}
                onChange={(e) => setValue(e.target.value)}
              >
                {status.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </TextField>
            </Stack>

            <Chart
              options={chartOptions}
              series={series}
              type="bar"
              height={480}
            />
          </Stack>
        </MainCard>
      )}
    </>
  );
};

export default TotalGrowthBarChart;
