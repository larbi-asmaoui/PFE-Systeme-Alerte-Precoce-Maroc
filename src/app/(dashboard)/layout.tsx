"use client";

import MainLayout from "@/layout/MainLayout";
import { ConfigProvider } from "@/contexts/ConfigContext";
import AuthGuard from "@/components/auth/AuthGuard";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ConfigProvider>
      <AuthGuard>
        <MainLayout>{children}</MainLayout>
      </AuthGuard>
    </ConfigProvider>
  );
}
