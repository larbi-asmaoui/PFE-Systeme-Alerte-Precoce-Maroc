import { ApexOptions } from 'apexcharts';

// ==============================|| DASHBOARD - BAJAJ AREA CHART ||============================== //

const chartOptions: ApexOptions = {
  chart: {
    id: 'support-chart',
    sparkline: {
      enabled: true
    },
    background: 'transparent', // Match original
    toolbar: {
      show: false
    }
  },
  dataLabels: {
    enabled: false
  },
  stroke: {
    curve: 'smooth',
    width: 1
  },
  yaxis: {
    labels: {
      show: false // match original 'min: 0' behavior if needed, but original code had just show: false
    }
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
        formatter: () => 'Ticket '
      }
    },
    marker: {
      show: false
    }
  }
};

export default chartOptions;
