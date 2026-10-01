"use client";

import type { ReactNode } from "react";
import { SaktiShell } from "@/components/sakti/SaktiShell";

/** The IP facilitator's desk. */
export default function Layout({ children }: { children: ReactNode }) {
  return <SaktiShell role="facilitator">{children}</SaktiShell>;
}
