import type { Role } from "@carebridge/shared-types";

/** Where each kind of account lands after signing in. */
export const HOME_FOR_ROLE: Record<Role, string> = {
  patient: "/home",
  doctor: "/clinician",
  admin: "/admin",
};

/** A doctor who is not approved yet lands here instead of the workspace. */
export const DOCTOR_APPLICATION_PATH = "/clinician/application";
