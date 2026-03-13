// ==============================|| OVERRIDES - AVATAR ||============================== //

export default function Avatar(theme) {
  return {
    MuiAvatar: {
      styleOverrides: {
        root: {
          // Define CSS variables for default colors
          '--avatar-default-color': theme.palette.background.paper, // Text color
          '--avatar-default-bg': theme.palette.primary[200],

          // Use the variables
          color: 'var(--avatar-default-color)',
          // background: 'linear-gradient(135deg, rgb(23, 62, 67) 50%, rgb(63, 176, 172) 50%)',
          opacity: 0.6,
        }
      }
    }
  };
}
