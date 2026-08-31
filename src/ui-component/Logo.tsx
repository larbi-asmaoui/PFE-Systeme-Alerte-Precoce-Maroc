// material-ui
import { useTheme } from "@mui/material/styles";
import { Typography, Box, Stack } from "@mui/material";

/**
 * Brand mark for the Early Warning System (Système d'Alerte Précoce — Maroc).
 * A rounded gradient shield with a warning glyph + a two-line wordmark. The
 * gradient runs warm→cool to echo the dashboard's heat/cold metrics.
 */
export default function Logo() {
  const theme = useTheme();
  const warm = theme.palette.error.main;
  const cool = theme.palette.info.main;

  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1.25 }}>
      <Stack spacing={0} sx={{ lineHeight: 1 }}>
        <Typography
          variant="h3"
          sx={{
            fontWeight: 800,
            letterSpacing: 0.5,
            color: theme.palette.grey[900],
            lineHeight: 1.05,
          }}
        >
          SAP{" "}
          <Box component="span" sx={{ color: warm }}>
            Maroc
          </Box>
        </Typography>
        <Typography
          variant="caption"
          sx={{
            color: theme.palette.text.secondary,
            fontWeight: 600,
            letterSpacing: 0.3,
            textTransform: "uppercase",
            fontSize: "0.6rem",
          }}
        >
          Système d&apos;Alerte Précoce
        </Typography>
      </Stack>
    </Box>
  );
}
