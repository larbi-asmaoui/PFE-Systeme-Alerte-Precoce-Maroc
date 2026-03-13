import { Theme, ThemeOptions } from '@mui/material/styles';
import { TypographyOptions } from '@mui/material/styles/createTypography';

declare module '@mui/material/styles' {
  interface CustomTheme extends Theme {
    customShadows: {
      z1: string;
      z8: string;
      z12: string;
      z16: string;
      z20: string;
      z24: string;
      primary: string;
      secondary: string;
      orange: string;
      success: string;
      warning: string;
      error: string;
    };
  }

  // Allow configuration using `createTheme`
  interface ThemeOptions {
    customShadows?: {
      z1?: string;
      z8?: string;
      z12?: string;
      z16?: string;
      z20?: string;
      z24?: string;
      primary?: string;
      secondary?: string;
      orange?: string;
      success?: string;
      warning?: string;
      error?: string;
    };
  }

  interface Palette {
    orange: Palette['primary'];
    dark: Palette['primary'] & {
      800: string;
      900: string;
    };
  }

  interface PaletteOptions {
    orange?: PaletteOptions['primary'];
    dark?: PaletteOptions['primary'] & {
      800?: string;
      900?: string;
    };
  }

  interface PaletteColor {
    200?: string;
    800?: string;
  }

  interface SimplePaletteColorOptions {
    200?: string;
    800?: string;
  }

  interface TypographyVariants {
    commonAvatar: React.CSSProperties;
    smallAvatar: React.CSSProperties;
    mediumAvatar: React.CSSProperties;
    largeAvatar: React.CSSProperties;
    menuCaption: React.CSSProperties;
    subMenuCaption: React.CSSProperties;
  }

  interface TypographyVariantsOptions {
    commonAvatar?: React.CSSProperties;
    smallAvatar?: React.CSSProperties;
    mediumAvatar?: React.CSSProperties;
    largeAvatar?: React.CSSProperties;
    menuCaption?: React.CSSProperties;
    subMenuCaption?: React.CSSProperties;
  }
}

// Update the Typography's variant prop options
declare module '@mui/material/Typography' {
  interface TypographyPropsVariantOverrides {
    commonAvatar: true;
    smallAvatar: true;
    mediumAvatar: true;
    largeAvatar: true;
    menuCaption: true;
    subMenuCaption: true;
  }
}
