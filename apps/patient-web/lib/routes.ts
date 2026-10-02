import type { Role } from "@carebridge/shared-types";

/**
 * Where each kind of account lands after signing in. One map for both products:
 * the paths never collide, and `/admin` is each product's own administration
 * (D-077, D-078). A product only ever signs in its own roles.
 */
export const HOME_FOR_ROLE: Record<Role, string> = {
  // CareBridge
  patient: "/home",
  doctor: "/clinician",
  // Both
  admin: "/admin",
  // IP-SAKTI Sahayak
  user: "/dashboard",
  facilitator: "/facilitator",
  curator: "/curator",
};

/** A doctor who is not approved yet lands here instead of the workspace. */
export const DOCTOR_APPLICATION_PATH = "/clinician/application";
