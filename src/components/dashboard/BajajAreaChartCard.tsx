import { useEffect, useState } from "react";
import { useTheme } from "@mui/material/styles";
import { Card, Grid, Typography } from "@mui/material";

import Chart from "@/ui-component/charts/Chart";

import chartData from "@/ui-component/chart-data/bajaj-area-chart";
import { useConfig } from "@/contexts/ConfigContext";

const BajajAreaChartCard = () => {
  const theme = useTheme();
  // @ts-ignore
  const { config } = useConfig();
  const { fontFamily } = config;

  const secondary800 = theme.palette.secondary[800];

  const [chartOptions, setChartOptions] =
    useState<ApexCharts.ApexOptions>(chartData);
  const [series] = useState([{ data: [0, 15, 10, 50, 30, 40, 25] }]);

  useEffect(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    setChartOptions((prevState: any) => ({
      ...prevState,
      chart: { ...prevState.chart, fontFamily: fontFamily },
      colors: [secondary800],
      fill: {
        gradient: {
          colorStops: [
            [
              { offset: 0, color: secondary800 ?? "#000", opacity: 0.4 },
              { offset: 100, color: secondary800 ?? "#000", opacity: 0.1 },
            ],
          ],
        },
      },
      theme: { mode: "light" },
    }));
  }, [fontFamily, secondary800]);

  return (
    <Card sx={{ bgcolor: "secondary.light", mt: -1 }}>
      <Grid container sx={{ p: 2, pb: 0, color: "#fff" }}>
        <Grid size={12}>
          <Grid container alignItems="center" justifyContent="space-between">
            <Grid>
              <Typography variant="subtitle1" sx={{ color: "secondary.dark" }}>
                Bajaj Finery
              </Typography>
            </Grid>
            <Grid>
              <Typography variant="h4" sx={{ color: "grey.800" }}>
                $1839.00
              </Typography>
            </Grid>
          </Grid>
        </Grid>
        <Grid size={12}>
          <Typography variant="subtitle2" sx={{ color: "grey.800" }}>
            10% Profit
          </Typography>
        </Grid>
      </Grid>
      <Chart options={chartOptions} series={series} type="area" height={95} />
    </Card>
  );
};

export default BajajAreaChartCard;
