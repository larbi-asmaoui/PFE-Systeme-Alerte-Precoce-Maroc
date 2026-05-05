// material-ui
import { styled, Theme } from "@mui/material/styles";

// project imports
import { drawerWidth } from "@/store/constant";

// ==============================|| MAIN LAYOUT - STYLED ||============================== //

interface MainContentStyledProps {
  theme: Theme;
  open: boolean;
  borderRadius: number;
}

const MainContentStyled = styled("main", {
  shouldForwardProp: (prop) => prop !== "open" && prop !== "borderRadius",
})<{ open: boolean; borderRadius: number }>(
  ({ theme, open, borderRadius }) => ({
    backgroundColor: theme.palette.grey[100],
    minWidth: "1%",
    width: "100%",
    minHeight: "calc(100vh - 88px)",
    flexGrow: 1,
    padding: "20px",
    marginTop: "88px",
    marginRight: "20px",
    borderRadius: `${borderRadius}px`,
    borderBottomLeftRadius: 0,
    borderBottomRightRadius: 0,
    ...(!open && {
      transition: theme.transitions.create("margin", {
        easing: theme.transitions.easing.sharp,
        duration: theme.transitions.duration.shorter + 200,
      }),
      [theme.breakpoints.up("md")]: {
        marginLeft: -(drawerWidth - 72),
        width: `calc(100% - ${drawerWidth}px)`,
        marginTop: "88px",
      },
    }),
    ...(open && {
      transition: theme.transitions.create("margin", {
        easing: theme.transitions.easing.easeOut,
        duration: theme.transitions.duration.shorter + 200,
      }),
      marginLeft: 0,
      marginTop: "88px",
      width: `calc(100% - ${drawerWidth}px)`,
      [theme.breakpoints.up("md")]: {
        marginTop: "88px",
      },
    }),
    [theme.breakpoints.down("md")]: {
      marginLeft: "20px",
      marginRight: "20px",
      padding: "16px",
      marginTop: "88px",
      width: "calc(100% - 40px)",
    },
    [theme.breakpoints.down("sm")]: {
      marginLeft: "10px",
      marginRight: "10px",
      padding: "16px",
      marginTop: "88px",
      width: "calc(100% - 20px)",
    },
  }),
);

export default MainContentStyled;
