"use client";

import AuthPageShell from "@/components/auth/AuthPageShell";
import LoginForm from "@/components/forms/LoginForm";

export default function LoginPage() {
  return (
    <AuthPageShell
      title="Bienvenue"
      subtitle="Entrez vos identifiants pour continuer"
      footerText="Vous n'avez pas de compte ?"
      footerLinkText="S'inscrire"
      footerLinkHref="/register"
    >
      <LoginForm />
    </AuthPageShell>
  );
}
