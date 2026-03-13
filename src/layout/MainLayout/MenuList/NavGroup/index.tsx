import { Fragment } from "react";

// material-ui
import { useTheme } from "@mui/material/styles";
import { Divider, List, Typography } from "@mui/material";

// project imports
import NavItem from "../NavItem";
import NavCollapse from "../NavCollapse";
import { MenuItem } from "@/menu-items";

interface NavGroupProps {
  item: MenuItem;
  drawerOpen: boolean;
}

export default function NavGroup({ item, drawerOpen }: NavGroupProps) {
  const theme = useTheme();

  // loop over children
  const items = item.children?.map((menu) => {
    switch (menu.type) {
      case "collapse":
        return (
          <NavCollapse
            key={menu.id}
            menu={menu}
            level={1}
            drawerOpen={drawerOpen}
          />
        );
      case "item":
        return (
          <NavItem
            key={menu.id}
            item={menu}
            level={1}
            drawerOpen={drawerOpen}
          />
        );
      default:
        return (
          <Typography key={menu.id} variant="h6" color="error" align="center">
            Menu Items Error
          </Typography>
        );
    }
  });

  return (
    <>
      <List
        subheader={
          item.title &&
          drawerOpen && (
            <Typography
              variant="caption"
              sx={{
                ...theme.typography.menuCaption,
                display: "block",
              }}
              gutterBottom
            >
              {item.title}
              {item.caption && (
                <Typography
                  variant="caption"
                  sx={{ ...theme.typography.subMenuCaption }}
                  display="block"
                  gutterBottom
                >
                  {item.caption}
                </Typography>
              )}
            </Typography>
          )
        }
      >
        {items}
      </List>

      {/* group divider */}
      <Divider sx={{ mt: 0.25, mb: 1.25 }} />
    </>
  );
}
