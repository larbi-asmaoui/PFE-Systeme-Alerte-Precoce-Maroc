import { ApexOptions } from 'apexcharts';

// ==============================|| DASHBOARD - TOTAL ORDER LINE CHART ||============================== //

const chartOptions: ApexOptions = {
  chart: {
    sparkline: {
      enabled: true
    }
  },
  dataLabels: {
    enabled: false
  },
  colors: ['#fff'],
  fill: {
    type: 'solid',
    opacity: 1
  },
  stroke: {
    curve: 'smooth',
    width: 3
  },
  yaxis: {
    min: 0,
    max: 100,
    labels: { show: false } // show: false to match original behavior
  },
  tooltip: {
    fixed: {
      enabled: false
    },
    x: {
      show: false
    },
    y: {
      title: {
        formatter: () => 'Total Order'
      }
    },
    marker: {
      show: false
    }
  }
};

export default chartOptions;
