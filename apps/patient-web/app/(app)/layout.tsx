"use client";

import type { ReactNode } from "react";
import { AppShell } from "@/components/AppShell";
import { ProductOnly } from "@/components/product/ProductOnly";

/** The patient area. CareBridge only: in IP-SAKTI every route here is a 404 (D-077). */
export default function AuthenticatedLayout({ children }: { children: ReactNode }) {
  return (
    <ProductOnly product="carebridge">
      <AppShell>{children}</AppShell>
    </ProductOnly>
  );
}
