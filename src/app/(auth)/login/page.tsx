"use client";

import AuthPageShell from "@/components/auth/AuthPageShell";
import LoginForm from "@/components/forms/LoginForm";

export default function LoginPage() {
  return (
    <AuthPageShell
      title="Welcome Back"
      subtitle="Enter your credentials to continue"
      footerText="Don't have an account?"
      footerLinkText="Sign Up"
      footerLinkHref="/register"
    >
      <LoginForm />
    </AuthPageShell>
  );
}
