"use client";

import * as React from "react";
import { createTheme, ThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import NextAppDirEmotionCacheProvider from "./EmotionCache";

// project imports
import buildPalette from "@/themes/palette";
import Typography from "@/themes/typography";
import CustomShadows from "@/themes/custom-shadows";
import ComponentsOverrides from "@/themes/overrides";
import { useConfig } from "@/contexts/ConfigContext"; // We'll create this later

// Define the theme creation logic directly or import it.
// Since we have the pieces, let's assemble them here to ensure everything is connected.

export default function ThemeRegistry({
  children,
}: {
  children: React.ReactNode;
}) {
  // In a real migration, we would use the Context to get these values.
  // For now, we will use defaults or fallback if Context isn't ready.
  // We need to implement ConfigContext first or mock it.
  // The layout wraps everything, so the ConfigProvider should likely wrap THIS or be inside.
  // Based on the prompt: "The Root Layout (layout.tsx) must be a Server Component... wrapping the app in the ThemeRegistry."
  // So ThemeRegistry is the top-level client component.

  // To avoid circular dependencies or missing context issues in this step, let's use default values
  // and plan for the ConfigContext integration.
  // However, the prompt says "Convert src/contexts/ConfigContext.jsx to TypeScript" in Step 2.
  // So we can assume it will exist.

  const DEFAULT_CONFIG = {
    fontFamily: `'Roboto', sans-serif`,
    borderRadius: 8,
    outlinedFilled: true,
    presetColor: "default",
  };

  const themeOptions = React.useMemo(() => {
    const palette = buildPalette(DEFAULT_CONFIG.presetColor);
    const themeTypography = Typography(DEFAULT_CONFIG.fontFamily);
    const customShadows = CustomShadows(palette as any);

    return {
      direction: "ltr",
      mixins: {
        toolbar: {
          minHeight: "48px",
          padding: "16px",
          "@media (min-width: 600px)": {
            minHeight: "48px",
          },
        },
      },
      palette: palette,
      typography: themeTypography,
      customShadows: customShadows,
    };
  }, []);

  const theme = createTheme(themeOptions as any);

  // Apply overrides
  theme.components = ComponentsOverrides(
    theme,
    DEFAULT_CONFIG.borderRadius,
    DEFAULT_CONFIG.outlinedFilled,
  );

  return (
    <NextAppDirEmotionCacheProvider options={{ key: "mui" }}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </NextAppDirEmotionCacheProvider>
  );
}
