"use client";

import { useAuth, useQuery } from "@carebridge/api-client/react";
import { useT } from "@carebridge/i18n";
import { Avatar, Button, ErrorState, LoadingState, Logo, cn } from "@carebridge/ui";
import { SignOut } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { DOCTOR_APPLICATION_PATH, HOME_FOR_ROLE } from "@/lib/routes";

const HOME = HOME_FOR_ROLE.doctor;

const NAV = [
  { href: HOME, key: "nav.dashboard" },
  { href: `${HOME}/profile`, key: "nav.profile" },
];

function Holding({ children }: { children: ReactNode }) {
  return <div className="mx-auto max-w-7xl px-4">{children}</div>;
}

/**
 * The clinician tool: ink chrome, dense content, no decoration. Same brand, same
 * type and colour system as the patient area — a different instrument.
 */
export function DoctorShell({ children }: { children: ReactNode }) {
  const { session, ready } = useAuth();
  const router = useRouter();
  const isDoctor = session?.user.role === "doctor";

  useEffect(() => {
    if (!ready) return;
    if (!session) router.replace("/login");
    else if (session.user.role !== "doctor") router.replace(HOME_FOR_ROLE[session.user.role]);
  }, [ready, session, router]);

  if (!ready || !isDoctor) {
    return (
      <Holding>
        <LoadingState />
      </Holding>
    );
  }
  return <ApprovedWorkspace>{children}</ApprovedWorkspace>;
}

/** The workspace opens only for an approved doctor. Anyone else is shown their application. */
function ApprovedWorkspace({ children }: { children: ReactNode }) {
  const { session, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const t = useT();
  const account = useQuery((a) => a.doctor.profile());
  const approved = account.data?.approval_status === "approved";

  useEffect(() => {
    if (account.data && !approved) router.replace(DOCTOR_APPLICATION_PATH);
  }, [account.data, approved, router]);

  if (account.error && !account.data) {
    return (
      <Holding>
        <ErrorState error={account.error} onRetry={account.reload} />
      </Holding>
    );
  }
  if (!approved || !session) {
    return (
      <Holding>
        <LoadingState />
      </Holding>
    );
  }

  const isActive = (href: string) =>
    href === HOME ? pathname === HOME || pathname.startsWith(`${HOME}/cases`) : pathname.startsWith(href);

  return (
    <div className="flex min-h-[100dvh] flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-4 focus:py-2 focus:shadow-md"
      >
        {t("a11y.skipToContent")}
      </a>

      <header className="sticky top-0 z-30 bg-ink text-white">
        <div className="mx-auto flex min-h-16 max-w-7xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-2.5 sm:px-6">
          <div className="flex items-center gap-6">
            <Link href={HOME} className="flex items-center gap-2.5 text-subheading tracking-tight">
              <Logo size={24} />
              <span>
                {t("app.name")}
                <span className="ml-1.5 font-normal text-white/60">{t("nav.clinician")}</span>
              </span>
            </Link>
            <nav aria-label={t("nav.main")}>
              <ul className="flex gap-1">
                {NAV.map((item) => {
                  const active = isActive(item.href);
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        aria-current={active ? "page" : undefined}
                        className={cn(
                          "inline-flex min-h-10 items-center rounded-md px-3 text-small font-medium transition-colors duration-150",
                          active ? "bg-white/15 text-white" : "text-white/70 hover:bg-white/10 hover:text-white",
                        )}
                      >
                        {t(item.key)}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden items-center gap-2 text-small text-white/75 md:flex">
              <Avatar name={session.user.email} size="sm" tone="ink" className="bg-white/15 text-white" />
              {session.user.email}
            </span>
            <Button variant="onDark" size="sm" onClick={logout}>
              <SignOut size={16} aria-hidden />
              {t("actions.signOut")}
            </Button>
          </div>
        </div>
      </header>

      <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:py-8">
        {children}
      </main>

      <footer className="border-t border-line bg-surface">
        <p className="mx-auto max-w-7xl px-4 py-4 text-small text-muted sm:px-6">{t("nav.policy")}</p>
      </footer>
    </div>
  );
}
