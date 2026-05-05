// material-ui
import { useTheme } from "@mui/material/styles";
import { Typography, Box } from "@mui/material";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";

export default function Logo() {
  const theme = useTheme();

  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
      <WarningAmberIcon
        sx={{ fontSize: 32, color: theme.palette.error.main }}
      />
      <Typography
        variant="h3"
        sx={{
          fontWeight: 800,
          color: theme.palette.grey[900],
          textTransform: "uppercase",
          letterSpacing: 1,
        }}
      >
        SAP <span style={{ color: theme.palette.error.main }}>Alerte</span>
      </Typography>
    </Box>
  );
}
