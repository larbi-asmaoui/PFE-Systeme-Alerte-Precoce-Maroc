/**
 * LoginForm – handles login form UI + submission logic.
 *
 * Validation: Zod schema via react-hook-form
 * Auth actions: delegated to AuthContext
 * Navigation: delegated to caller or useRouter
 */

"use client";

import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Typography,
} from "@mui/material";
import { useRouter } from "next/navigation";

import { useAuth } from "@/contexts/AuthContext";
import { loginSchema, type LoginFormValues } from "@/lib/validations/auth";
import { ApiClientError } from "@/services/api";
import FormTextField from "@/components/forms/FormTextField";
import PasswordField from "@/components/forms/PasswordField";

export default function LoginForm() {
  const router = useRouter();
  const { login } = useAuth();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    control,
    handleSubmit,
    formState: { isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
    mode: "onBlur",
  });

  const onSubmit = async (data: LoginFormValues) => {
    setServerError(null);
    try {
      await login(data);
      router.replace("/");
    } catch (err) {
      if (err instanceof ApiClientError) {
        setServerError(err.detail);
      } else {
        setServerError("An unexpected error occurred. Please try again.");
      }
    }
  };

  return (
    <Box component="form" onSubmit={handleSubmit(onSubmit)} noValidate>
      {serverError && (
        <Alert
          severity="error"
          sx={{ mb: 2 }}
          onClose={() => setServerError(null)}
        >
          {serverError}
        </Alert>
      )}

      <FormTextField<LoginFormValues>
        name="email"
        control={control}
        label="Email Address"
        type="email"
        fullWidth
        autoComplete="email"
        autoFocus
        sx={{ mb: 2.5 }}
      />

      <PasswordField<LoginFormValues>
        name="password"
        control={control}
        label="Password"
        fullWidth
        autoComplete="current-password"
        sx={{ mb: 1 }}
      />

      <Box sx={{ textAlign: "right", mb: 2 }}>
        <Typography
          variant="caption"
          color="secondary"
          sx={{ cursor: "pointer" }}
        >
          Forgot Password?
        </Typography>
      </Box>

      <Button
        type="submit"
        fullWidth
        variant="contained"
        color="secondary"
        size="large"
        disabled={isSubmitting}
        sx={{
          height: 48,
          borderRadius: 2,
          fontWeight: 600,
          textTransform: "none",
          fontSize: "1rem",
        }}
      >
        {isSubmitting ? (
          <CircularProgress size={24} color="inherit" />
        ) : (
          "Sign In"
        )}
      </Button>
    </Box>
  );
}
