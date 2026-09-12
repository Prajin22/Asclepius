"use client";

import { AuthProvider } from "@carebridge/api-client/react";
import type { ReactNode } from "react";
import { LocaleProvider } from "@/lib/locale";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/**
 * One app for patients, doctors and administrators. Everyone signs in here and
 * is routed by the role on their account; the API checks that role on every request.
 */
export function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider baseUrl={API_BASE_URL} storageKey="asclepius.session">
      <LocaleProvider>{children}</LocaleProvider>
    </AuthProvider>
  );
}
