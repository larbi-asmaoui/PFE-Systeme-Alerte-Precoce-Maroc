// ==============================|| OVERRIDES - LIST ITEM BUTTON ||============================== //

export default function ListItemButton(theme) {
  return {
    MuiListItemButton: {
      styleOverrides: {
        root: {
          color: theme.palette.text.primary,
          paddingTop: '10px',
          paddingBottom: '10px',

          '&.Mui-selected': {
            color: theme.palette.secondary.dark,
            backgroundColor: theme.palette.secondary.light,
            '&:hover': {
              backgroundColor: theme.palette.secondary.light
            },
            '& .MuiListItemIcon-root': {
              color: theme.palette.secondary.dark
            }
          },

          '&:hover': {
            backgroundColor: theme.palette.secondary.light,
            color: theme.palette.secondary.dark,
            '& .MuiListItemIcon-root': {
              color: theme.palette.secondary.dark
            }
          }
        }
      }
    }
  };
}
