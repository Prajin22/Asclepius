import type { ReactNode } from "react";
import { ProductOnly } from "@/components/product/ProductOnly";

/**
 * Everything under /clinician — the workspace and the doctor application. CareBridge
 * only: in IP-SAKTI every route here is a 404 (D-077). Nothing below this file changes.
 */
export default function ClinicianLayout({ children }: { children: ReactNode }) {
  return <ProductOnly product="carebridge">{children}</ProductOnly>;
}
