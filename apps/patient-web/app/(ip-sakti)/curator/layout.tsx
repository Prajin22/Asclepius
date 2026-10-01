"use client";

import type { ReactNode } from "react";
import { SaktiShell } from "@/components/sakti/SaktiShell";

/** The corpus curator's area. */
export default function Layout({ children }: { children: ReactNode }) {
  return <SaktiShell role="curator">{children}</SaktiShell>;
}
