/**
 * The product boundary in the route tree (D-077).
 *
 * `ProductOnly` wraps a whole area: in the other product, every route under it
 * does not exist (404) — not hidden behind a check, not redirected somewhere
 * plausible. `forProduct` picks one screen per product for the three paths both
 * products share: `/`, `/login` and `/admin`.
 *
 * Healthcare screens are not deleted or moved: in a CareBridge build they render
 * exactly as before.
 */
import type { Product } from "@carebridge/shared-types";
import { notFound } from "next/navigation";
import type { ComponentType, ReactNode } from "react";
import { PRODUCT } from "@/lib/product";

export function ProductOnly({
  product,
  current = PRODUCT,
  children,
}: {
  product: Product;
  /** For tests; a build always uses its own product. */
  current?: Product;
  children: ReactNode;
}) {
  if (product !== current) notFound();
  return <>{children}</>;
}

export function forProduct<P extends object>(
  screens: Record<Product, ComponentType<P>>,
  current: Product = PRODUCT,
): ComponentType<P> {
  return screens[current];
}
