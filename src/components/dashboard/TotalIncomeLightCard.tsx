// material-ui
import { useTheme, styled } from "@mui/material/styles";
import {
  Avatar,
  Box,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  Typography,
} from "@mui/material";

import MainCard from "@/ui-component/cards/MainCard";
import TotalIncomeCardSkeleton from "@/ui-component/cards/Skeleton/TotalIncomeCard";
import { withAlpha } from "@/utils/colorUtils";

const CardWrapper = styled(MainCard)(({ theme }) => ({
  overflow: "hidden",
  position: "relative",
  "&:after": {
    content: '""',
    position: "absolute",
    width: 210,
    height: 210,
    background: `linear-gradient(210.04deg, ${theme.palette.warning.dark} -50.94%, rgba(144, 202, 249, 0) 83.49%)`,
    borderRadius: "50%",
    top: -30,
    right: -180,
  },
  "&:before": {
    content: '""',
    position: "absolute",
    width: 210,
    height: 210,
    background: `linear-gradient(140.9deg, ${theme.palette.warning.dark} -14.02%, rgba(144, 202, 249, 0) 70.50%)`,
    borderRadius: "50%",
    top: -160,
    right: -130,
  },
}));

interface TotalIncomeLightCardProps {
  isLoading?: boolean;
  total: number;
  icon: React.ReactNode;
  label: string;
}

const TotalIncomeLightCard = ({
  isLoading,
  total,
  icon,
  label,
}: TotalIncomeLightCardProps) => {
  const theme = useTheme();

  return (
    <>
      {isLoading ? (
        <TotalIncomeCardSkeleton />
      ) : (
        <CardWrapper border={false} content={false}>
          <Box sx={{ p: 2 }}>
            <List sx={{ py: 0 }}>
              <ListItem alignItems="center" disableGutters sx={{ py: 0 }}>
                <ListItemAvatar>
                  <Avatar
                    variant="rounded"
                    sx={{
                      ...theme.typography.largeAvatar,
                      borderRadius: "8px",
                      bgcolor:
                        label === "Meeting attends"
                          ? withAlpha(theme.palette.error.light, 0.25)
                          : "warning.light",
                      color:
                        label === "Meeting attends"
                          ? "error.dark"
                          : "warning.dark",
                    }}
                  >
                    {icon}
                  </Avatar>
                </ListItemAvatar>
                <ListItemText
                  sx={{ py: 0, mt: 0.45, mb: 0.45 }}
                  primary={<Typography variant="h4">${total}k</Typography>}
                  secondary={
                    <Typography
                      variant="subtitle2"
                      sx={{ color: "grey.500", mt: 0.5 }}
                    >
                      {label}
                    </Typography>
                  }
                />
              </ListItem>
            </List>
          </Box>
        </CardWrapper>
      )}
    </>
  );
};

export default TotalIncomeLightCard;
