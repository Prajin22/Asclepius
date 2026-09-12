"use client";

import type { ReactNode } from "react";
import { DoctorShell } from "@/components/DoctorShell";

export default function AuthenticatedLayout({ children }: { children: ReactNode }) {
  return <DoctorShell>{children}</DoctorShell>;
}
