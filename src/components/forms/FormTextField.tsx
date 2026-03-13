/**
 * FormTextField – MUI TextField wired to react-hook-form's Controller.
 *
 * Reusable across any form. Accepts all MUI TextField props
 * plus the RHF control & field name.
 */

"use client";

import { Controller, Control, FieldValues, Path } from "react-hook-form";
import { TextField, TextFieldProps } from "@mui/material";

type FormTextFieldProps<T extends FieldValues> = {
  name: Path<T>;
  control: Control<T>;
} & Omit<TextFieldProps, "name">;

export default function FormTextField<T extends FieldValues>({
  name,
  control,
  ...textFieldProps
}: FormTextFieldProps<T>) {
  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState: { error } }) => (
        <TextField
          {...field}
          {...textFieldProps}
          error={!!error}
          helperText={error?.message ?? textFieldProps.helperText}
        />
      )}
    />
  );
}
