// third party
import { merge } from "lodash-es";
import { Theme } from "@mui/material/styles";

// project imports
import Alert from "./Alert";
import Avatar from "./Avatar";
import Button from "./Button";
import CardActions from "./CardActions";
import CardContent from "./CardContent";
import CardHeader from "./CardHeader";
import Checkbox from "./Checkbox";
import Chip from "./Chip";
import Divider from "./Divider";
import Dialog from "./Dialog";
import DialogTitle from "./DialogTitle";
import InputBase from "./InputBase";
import ListItemButton from "./ListItemButton";
import ListItemIcon from "./ListItemIcon";
import ListItemText from "./ListItemText";
import Paper from "./Paper";
import Select from "./Select";
import TableCell from "./TableCell";
import Typography from "./Typography";

export default function ComponentsOverrides(
  theme: Theme,
  borderRadius: number,
  outlinedFilled: boolean,
) {
  return merge(
    Alert(theme),
    Avatar(theme),
    Button(theme),
    CardActions(),
    CardContent(),
    CardHeader(theme),
    Checkbox(),
    Chip(theme),
    Dialog(),
    DialogTitle(),
    Divider(theme),
    InputBase(theme),
    ListItemButton(theme),
    ListItemIcon(theme),
    ListItemText(theme),
    Paper(borderRadius),
    Select(),
    TableCell(theme),
    Typography(theme),
  );
}
