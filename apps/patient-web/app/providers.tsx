"use client";

import { AuthProvider } from "@carebridge/api-client/react";
import type { ReactNode } from "react";
import { LocaleProvider } from "@/lib/locale";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider baseUrl={API_BASE_URL} storageKey="carebridge.patient.session" expectedRole="patient">
      <LocaleProvider>{children}</LocaleProvider>
    </AuthProvider>
  );
}
