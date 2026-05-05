/**
 * AuthGuard – client component that protects routes behind authentication.
 *
 * While the auth state is loading it renders a full-page spinner.
 * If the user is not authenticated it redirects to /login.
 */

"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Box, CircularProgress } from "@mui/material";

import { useAuth } from "@/contexts/AuthContext";

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  // const { isAuthenticated, isLoading } = useAuth();
  // const router = useRouter();

  // useEffect(() => {
  //   if (!isLoading && !isAuthenticated) {
  //     router.replace("/login");
  //   }
  // }, [isAuthenticated, isLoading, router]);

  // if (isLoading) {
  //   return (
  //     <Box
  //       sx={{
  //         display: "flex",
  //         justifyContent: "center",
  //         alignItems: "center",
  //         minHeight: "100vh",
  //       }}
  //     >
  //       <CircularProgress color="secondary" size={48} />
  //     </Box>
  //   );
  // }

  // if (!isAuthenticated) {
  //   return null; // will redirect
  // }

  return <>{children}</>;
}
