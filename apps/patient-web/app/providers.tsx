"use client";

import { AuthProvider } from "@carebridge/api-client/react";
import type { ReactNode } from "react";
import { LocaleProvider } from "@/lib/locale";
import { productConfig } from "@/lib/product";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/**
 * One app for every role of the product this build serves. Everyone signs in
 * here and is routed by the role on their account; the API checks that role,
 * and that the token is this product's, on every request.
 */
export function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider baseUrl={API_BASE_URL} storageKey={productConfig.sessionKey}>
      <LocaleProvider>{children}</LocaleProvider>
    </AuthProvider>
  );
}
