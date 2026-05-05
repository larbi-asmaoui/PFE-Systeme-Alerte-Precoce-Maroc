// FILE: src/components/map/HeatMap.tsx
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css"; // MUST import Leaflet CSS
import { Box, Typography } from "@mui/material";

interface RegionData {
  id: number;
  name: string;
  coords: [number, number];
  alert: string;
  temp: number;
}

interface HeatMapProps {
  regions: RegionData[];
}

const alertColors: Record<string, string> = {
  red: "#d32f2f",
  orange: "#ed6c02",
  yellow: "#ffeb3b",
  none: "#e0e0e0",
};

export default function HeatMap({ regions }: HeatMapProps) {
  return (
    // zIndex: 0 ensures the map stays behind your floating Material-UI papers
    <Box
      sx={{
        height: "100%",
        width: "100%",
        position: "absolute",
        top: 0,
        left: 0,
        zIndex: 0,
      }}
    >
      <MapContainer
        {...{
          center: [31.7917, -7.0926] as [number, number],
          zoom: 6,
          zoomControl: false,
          style: { height: "100%", width: "100%" },
        }}
      >
        {/* Clean, light-grey map tiles to make weather data pop */}
        <TileLayer
          {...{
            url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>'
          }}
        />

        {/* Draw circles for each region */}
        {regions.map((region) => (
          <CircleMarker
            key={region.id}
            {...{
              center: region.coords,
              radius: region.alert === "red" ? 25 : region.alert === "orange" ? 18 : 12,
            }}
            pathOptions={{
              color: alertColors[region.alert],
              fillColor: alertColors[region.alert],
              fillOpacity: 0.6,
              weight: 2,
            }}
          >
            <Popup>
              <Typography variant="subtitle2" fontWeight="bold">
                {region.name}
              </Typography>
              <Typography variant="body2" color="error">
                {region.temp}°C Prévu
              </Typography>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </Box>
  );
}
