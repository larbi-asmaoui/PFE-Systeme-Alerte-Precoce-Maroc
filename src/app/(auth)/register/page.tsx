"use client";

import AuthPageShell from "@/components/auth/AuthPageShell";
import RegisterForm from "@/components/forms/RegisterForm";

export default function RegisterPage() {
  return (
    <AuthPageShell
      title="Créer un compte"
      subtitle="Inscrivez-vous pour commencer"
      footerText="Vous avez déjà un compte ?"
      footerLinkText="Se connecter"
      footerLinkHref="/login"
    >
      <RegisterForm />
    </AuthPageShell>
  );
}
