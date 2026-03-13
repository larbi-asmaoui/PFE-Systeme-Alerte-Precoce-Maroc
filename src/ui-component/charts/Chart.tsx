"use client";

import dynamic from "next/dynamic";
import { Props as ApexProps } from "react-apexcharts";

// Dynamically import react-apexcharts with no SSR to avoid "window is not defined" error
const ReactApexChart = dynamic(() => import("react-apexcharts"), {
  ssr: false,
  loading: () => null, // Optional: loading component
});

export default function Chart(props: ApexProps) {
  return <ReactApexChart {...props} />;
}
