"use client";

import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Alert, Box, Button, CircularProgress, Grid } from "@mui/material";
import { useRouter } from "next/navigation";

import { useAuth } from "@/contexts/AuthContext";
import {
  registerSchema,
  type RegisterFormValues,
} from "@/lib/validations/auth";
import { ApiClientError } from "@/services/api";
import FormTextField from "@/components/forms/FormTextField";
import PasswordField from "@/components/forms/PasswordField";

export default function RegisterForm() {
  const router = useRouter();
  const { register: registerUser } = useAuth();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    control,
    handleSubmit,
    formState: { isSubmitting },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { first_name: "", last_name: "", email: "", password: "" },
    mode: "onBlur",
  });

  const onSubmit = async (data: RegisterFormValues) => {
    setServerError(null);
    try {
      await registerUser(data);
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

      <Grid container spacing={2} sx={{ mb: 2 }}>
        <Grid size={{ xs: 12, sm: 6 }}>
          <FormTextField<RegisterFormValues>
            name="first_name"
            control={control}
            label="First Name"
            fullWidth
            autoFocus
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <FormTextField<RegisterFormValues>
            name="last_name"
            control={control}
            label="Last Name"
            fullWidth
          />
        </Grid>
      </Grid>

      <FormTextField<RegisterFormValues>
        name="email"
        control={control}
        label="Email Address"
        type="email"
        fullWidth
        autoComplete="email"
        sx={{ mb: 2.5 }}
      />

      <PasswordField<RegisterFormValues>
        name="password"
        control={control}
        label="Password"
        fullWidth
        autoComplete="new-password"
        helperText="Must be 8+ chars with uppercase, lowercase & number"
        sx={{ mb: 3 }}
      />

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
          "Create Account"
        )}
      </Button>
    </Box>
  );
}
