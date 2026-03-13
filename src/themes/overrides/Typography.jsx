// ==============================|| OVERRIDES - TYPOGRAPHY ||============================== //

export default function Typography(theme) {
  const headingColor = theme.palette.text.heading;

  return {
    MuiTypography: {
      styleOverrides: {
        root: {
          variants: [
            {
              props: { variant: 'h1' },
              style: { color: headingColor }
            },
            {
              props: { variant: 'h2' },
              style: { color: headingColor }
            },
            {
              props: { variant: 'h3' },
              style: { color: headingColor }
            },
            {
              props: { variant: 'h4' },
              style: { color: headingColor }
            },
            {
              props: { variant: 'h5' },
              style: { color: headingColor }
            },
            {
              props: { variant: 'h6' },
              style: { color: headingColor }
            },
            {
              props: { variant: 'subtitle1' },
              style: { color: theme.palette.text.dark }
            },
            {
              props: { variant: 'subtitle2' },
              style: { color: theme.palette.text.secondary }
            },
            {
              props: { variant: 'caption' },
              style: { color: theme.palette.text.secondary }
            },
            {
              props: { variant: 'body2' },
              style: { color: theme.palette.text.primary }
            }
          ]
        }
      }
    }
  };
}
