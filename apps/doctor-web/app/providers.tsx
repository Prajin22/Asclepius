"use client";

import { AuthProvider } from "@carebridge/api-client/react";
import { I18nProvider } from "@carebridge/i18n";
import { doctorCatalogs } from "@carebridge/i18n/catalogs";
import type { ReactNode } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** Clinician UI is English in Phase 1; strings still come from the catalogue. */
const UI_LOCALE = "en";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider baseUrl={API_BASE_URL} storageKey="carebridge.doctor.session" expectedRole="doctor">
      <I18nProvider locale={UI_LOCALE} catalogs={doctorCatalogs}>
        {children}
      </I18nProvider>
    </AuthProvider>
  );
}
