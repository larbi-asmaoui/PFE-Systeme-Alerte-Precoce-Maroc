import React from "react";

// material-ui
import { useTheme } from "@mui/material/styles";
import {
  Avatar,
  Button,
  Card,
  Chip,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  Stack,
  Typography,
  Box,
} from "@mui/material";

// project imports
import { withAlpha } from "@/utils/colorUtils";

// assets
import {
  IconBrandTelegram,
  IconBuildingStore,
  IconMailbox,
  IconPhoto,
} from "@tabler/icons-react";

const ListItemWrapper = ({ children }: { children: React.ReactNode }) => {
  const theme = useTheme();

  return (
    <Box
      sx={{
        p: 2,
        borderBottom: "1px solid",
        borderColor: "divider",
        cursor: "pointer",
        "&:hover": {
          bgcolor: withAlpha(theme.palette.grey[200], 0.3),
        },
      }}
    >
      {children}
    </Box>
  );
};

// ==============================|| NOTIFICATION LIST ITEM ||============================== //

export default function NotificationList() {
  const containerSX = { gap: 2, pl: 7 };

  return (
    <List sx={{ width: "100%", maxWidth: { xs: 300, md: 330 }, py: 0 }}>
      <ListItemWrapper>
        <ListItem
          alignItems="center"
          disablePadding
          secondaryAction={
            <Stack
              direction="row"
              alignItems="center"
              justifyContent="flex-end"
            >
              <Typography variant="caption">il y a 2 min</Typography>
            </Stack>
          }
        >
          <ListItemAvatar>
            <Avatar alt="John Doe" src="/assets/images/users/user-round.svg" />
          </ListItemAvatar>
          <ListItemText primary="John Doe" />
        </ListItem>
        <Stack sx={containerSX}>
          <Typography variant="subtitle2">
            Il est un fait bien établi qu'un lecteur sera distrait
          </Typography>
          <Stack direction="row" alignItems="center" sx={{ gap: 1 }}>
            <Chip
              label="Non lu"
              color="error"
              size="small"
              sx={{ width: "min-content" }}
            />
            <Chip
              label="New"
              color="warning"
              size="small"
              sx={{ width: "min-content" }}
            />
          </Stack>
        </Stack>
      </ListItemWrapper>
      <ListItemWrapper>
        <ListItem
          alignItems="center"
          disablePadding
          secondaryAction={
            <Stack
              direction="row"
              alignItems="center"
              justifyContent="flex-end"
            >
              <Typography variant="caption">il y a 2 min</Typography>
            </Stack>
          }
        >
          <ListItemAvatar>
            <Avatar
              sx={{
                color: "success.dark",
                bgcolor: "success.light",
              }}
            >
              <IconBuildingStore stroke={1.5} size={20} />
            </Avatar>
          </ListItemAvatar>
          <ListItemText
            primary={
              <Typography variant="subtitle1">
                Vérification de la boutique effectuée
              </Typography>
            }
          />
        </ListItem>
        <Stack sx={containerSX}>
          <Typography variant="subtitle2">
            Nous avons bien reçu votre demande.
          </Typography>
          <Chip
            label="Non lu"
            color="error"
            size="small"
            sx={{ width: "min-content" }}
          />
        </Stack>
      </ListItemWrapper>
      <ListItemWrapper>
        <ListItem
          alignItems="center"
          disablePadding
          secondaryAction={
            <Stack
              direction="row"
              alignItems="center"
              justifyContent="flex-end"
            >
              <Typography variant="caption">il y a 2 min</Typography>
            </Stack>
          }
        >
          <ListItemAvatar>
            <Avatar
              sx={{
                color: "primary.dark",
                bgcolor: "primary.light",
              }}
            >
              <IconMailbox stroke={1.5} size={20} />
            </Avatar>
          </ListItemAvatar>
          <ListItemText
            primary={
              <Typography variant="subtitle1">Vérifiez votre messagerie.</Typography>
            }
          />
        </ListItem>
        <Stack sx={containerSX}>
          <Typography variant="subtitle2">
            All done! Now check your inbox as you&apos;re in for a sweet treat!
          </Typography>
          <Button
            variant="contained"
            endIcon={<IconBrandTelegram stroke={1.5} size={20} />}
            sx={{ width: "min-content" }}
          >
            Mail
          </Button>
        </Stack>
      </ListItemWrapper>
      <ListItemWrapper>
        <ListItem
          alignItems="center"
          disablePadding
          secondaryAction={
            <Stack
              direction="row"
              alignItems="center"
              justifyContent="flex-end"
            >
              <Typography variant="caption">il y a 2 min</Typography>
            </Stack>
          }
        >
          <ListItemAvatar>
            <Avatar alt="John Doe" src="/assets/images/users/user-round.svg" />
          </ListItemAvatar>
          <ListItemText
            primary={<Typography variant="subtitle1">John Doe</Typography>}
          />
        </ListItem>
        <Stack sx={containerSX}>
          <Typography component="span" variant="subtitle2">
            a importé deux fichiers le &nbsp;
            <Typography component="span" variant="h6">
              21 Jan 2020
            </Typography>
          </Typography>
          <Card sx={{ bgcolor: "secondary.light" }}>
            <Stack direction="row" sx={{ p: 2.5, gap: 2 }}>
              <IconPhoto stroke={1.5} size={20} />
              <Typography variant="subtitle1">demo.jpg</Typography>
            </Stack>
          </Card>
        </Stack>
      </ListItemWrapper>
      <ListItemWrapper>
        <ListItem
          alignItems="center"
          disablePadding
          secondaryAction={
            <Stack
              direction="row"
              alignItems="center"
              justifyContent="flex-end"
            >
              <Typography variant="caption">il y a 2 min</Typography>
            </Stack>
          }
        >
          <ListItemAvatar>
            <Avatar alt="John Doe" src="/assets/images/users/user-round.svg" />
          </ListItemAvatar>
          <ListItemText
            primary={<Typography variant="subtitle1">John Doe</Typography>}
          />
        </ListItem>
        <Stack sx={containerSX}>
          <Typography variant="subtitle2">
            Il est un fait bien établi qu'un lecteur sera distrait
          </Typography>
          <Chip
            label="Confirmation de compte."
            color="success"
            size="small"
            sx={{ width: "min-content" }}
          />
        </Stack>
      </ListItemWrapper>
    </List>
  );
}
