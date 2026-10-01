import type { ReactNode } from "react";
import { ProductOnly } from "@/components/product/ProductOnly";

/** Every IP-SAKTI Sahayak screen. In a CareBridge build none of them exists (D-077). */
export default function IpSaktiLayout({ children }: { children: ReactNode }) {
  return <ProductOnly product="ip_sakti">{children}</ProductOnly>;
}
