import Link from "next/link";

import { Link as MuiLink } from "@mui/material";

import { DASHBOARD_PATH } from "@/config";
import Logo from "@/ui-component/Logo";

export default function LogoSection() {
  return (
    <Link href={DASHBOARD_PATH} passHref>
      <MuiLink aria-label="theme-logo" sx={{ display: "block" }}>
        <Logo />
      </MuiLink>
    </Link>
  );
}
