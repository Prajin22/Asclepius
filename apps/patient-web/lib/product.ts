/**
 * Which product this build is, and what that product is (D-077).
 *
 * `NEXT_PUBLIC_PRODUCT` is inlined at build time, so one build serves exactly
 * one product. Unset means CareBridge, exactly as before; an unknown value
 * fails the build rather than silently shipping the wrong product.
 *
 * Server-safe on purpose: no catalogues and no client-only imports, because the
 * root layout reads this to set the page title and theme. The catalogue for each
 * product is chosen in `lib/locale.tsx`.
 */
import { PRODUCTS, ROLES_BY_PRODUCT, isProduct, type Product, type Role } from "@carebridge/shared-types";

export function parseProduct(value: string | undefined): Product {
  if (value === undefined || value.trim() === "") return "carebridge";
  if (isProduct(value)) return value;
  throw new Error(`NEXT_PUBLIC_PRODUCT=${JSON.stringify(value)} is not a product. Use one of: ${PRODUCTS.join(", ")}.`);
}

export const PRODUCT: Product = parseProduct(process.env.NEXT_PUBLIC_PRODUCT);
export const IS_IP_SAKTI = PRODUCT === "ip_sakti";

export interface ProductConfig {
  product: Product;
  /** For the document title and metadata, which sit outside the i18n tree. */
  name: string;
  description: string;
  /** Browser chrome colour; matches the product's brand token in globals.css. */
  themeColor: string;
  roles: readonly Role[];
  /** sessionStorage key for the signed-in session. Distinct per product, so a
   *  session from one product is never picked up by the other on one origin. */
  sessionKey: string;
  /** localStorage key for the chosen interface language. */
  localeKey: string;
}

export const PRODUCT_CONFIGS: Record<Product, ProductConfig> = {
  carebridge: {
    product: "carebridge",
    name: "Asclepius",
    description: "Your health information, organised — in your own words, shared on your terms.",
    themeColor: "#d83a2e",
    roles: ROLES_BY_PRODUCT.carebridge,
    // Unchanged from before the product boundary, so existing sessions and
    // language choices survive.
    sessionKey: "asclepius.session",
    localeKey: "carebridge.patient.locale",
  },
  ip_sakti: {
    product: "ip_sakti",
    name: "IP-SAKTI Sahayak",
    description:
      "Intellectual Property & Regulatory Guidance for Ayurvedic Products. Information grounded in cited sources — not legal advice.",
    themeColor: "#0e5f63",
    roles: ROLES_BY_PRODUCT.ip_sakti,
    sessionKey: "ipsakti.session",
    localeKey: "ipsakti.locale",
  },
};

export const productConfig: ProductConfig = PRODUCT_CONFIGS[PRODUCT];

/** Whether an account holding `role` belongs in this product. */
export function acceptsRole(role: Role, product: Product = PRODUCT): boolean {
  return (ROLES_BY_PRODUCT[product] as readonly Role[]).includes(role);
}
