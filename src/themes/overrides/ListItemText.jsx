// ==============================|| OVERRIDES - LIST ITEM TEXT ||============================== //

export default function ListItemText(theme) {
  return {
    MuiListItemText: {
      styleOverrides: {
        primary: {
          color: theme.palette.text.dark
        }
      }
    }
  };
}
