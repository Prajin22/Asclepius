"use client";

import { I18nProvider } from "@carebridge/i18n";
import { doctorCatalogs } from "@carebridge/i18n/catalogs";
import type { ReactNode } from "react";
import { DoctorShell } from "@/components/clinician/DoctorShell";

/** The clinician workspace is English in this prototype; its strings still come from a catalogue. */
export default function ClinicianWorkspaceLayout({ children }: { children: ReactNode }) {
  return (
    <I18nProvider locale="en" catalogs={doctorCatalogs}>
      <div lang="en">
        <DoctorShell>{children}</DoctorShell>
      </div>
    </I18nProvider>
  );
}
