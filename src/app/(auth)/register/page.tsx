"use client";

import AuthPageShell from "@/components/auth/AuthPageShell";
import RegisterForm from "@/components/forms/RegisterForm";

export default function RegisterPage() {
  return (
    <AuthPageShell
      title="Create Account"
      subtitle="Sign up to get started"
      footerText="Already have an account?"
      footerLinkText="Sign In"
      footerLinkHref="/login"
    >
      <RegisterForm />
    </AuthPageShell>
  );
}
