"use client";

import type { ReactNode } from "react";
import { SaktiShell } from "@/components/sakti/SaktiShell";

/** The user's area: ask, classify, describe a product, escalate. */
export default function Layout({ children }: { children: ReactNode }) {
  return <SaktiShell role="user">{children}</SaktiShell>;
}
