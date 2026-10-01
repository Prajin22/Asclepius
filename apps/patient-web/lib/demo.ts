/** Synthetic demo accounts created by `python -m app.seed`. Not real people. */
export const DEMO_ACCOUNTS = {
  patient: { email: "arun.kumar@carebridge.demo", password: "Patient@2026" },
  doctor: { email: "meera.sharma@carebridge.demo", password: "Doctor@2026" },
  // Signed up and waiting for an administrator, so the application screen can be seen.
  pendingDoctor: { email: "kavya.nair@carebridge.demo", password: "Doctor@2026" },
} as const;

export type DemoAccountKey = keyof typeof DEMO_ACCOUNTS;

/** IP-SAKTI Sahayak's synthetic accounts, one per role (`backend/app/sakti/seed.py`). */
export const SAKTI_DEMO_ACCOUNTS = [
  { role: "user", email: "user@ipsakti.demo", password: "User@2026" },
  { role: "facilitator", email: "facilitator@ipsakti.demo", password: "Facilitator@2026" },
  { role: "curator", email: "curator@ipsakti.demo", password: "Curator@2026" },
  { role: "admin", email: "admin@ipsakti.demo", password: "Admin@2026" },
] as const;

export const SHOW_DEMO_ACCOUNT = process.env.NEXT_PUBLIC_SHOW_DEMO_ACCOUNTS !== "false";
