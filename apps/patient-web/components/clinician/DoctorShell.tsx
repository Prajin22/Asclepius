"use client";

import { useAuth, useQuery } from "@carebridge/api-client/react";
import { useT } from "@carebridge/i18n";
import { Button, ErrorState, LoadingState, Logo, cn } from "@carebridge/ui";
import { SignOut } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ComponentProps, type ReactNode } from "react";
import { ChatIcon, HomeIcon, PeopleIcon, UserIcon } from "@/components/icons";
import { DOCTOR_APPLICATION_PATH, HOME_FOR_ROLE } from "@/lib/routes";

const HOME = HOME_FOR_ROLE.doctor;

type NavIcon = (props: ComponentProps<typeof HomeIcon>) => ReactNode;

/** Four destinations: what needs you, who you see, every consultation, your profile. */
const NAV: { href: string; key: string; Icon: NavIcon }[] = [
  { href: HOME, key: "nav.home", Icon: HomeIcon },
  { href: `${HOME}/patients`, key: "nav.patients", Icon: PeopleIcon },
  { href: `${HOME}/consultations`, key: "nav.consultations", Icon: ChatIcon },
  { href: `${HOME}/profile`, key: "nav.profile", Icon: UserIcon },
];

function Holding({ children }: { children: ReactNode }) {
  return <div className="mx-auto max-w-7xl px-4">{children}</div>;
}

/**
 * The clinician tool: ink chrome, dense content, no decoration. Same sheet, same
 * type and same fold language as the patient area — a different instrument.
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
    href === HOME ? pathname === HOME : pathname.startsWith(href) || (href.endsWith("/consultations") && pathname.startsWith(`${HOME}/cases`));

  return (
    <div className="flex min-h-[100dvh] flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-3 focus:z-50 focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:shadow-md"
      >
        {t("a11y.skipToContent")}
      </a>

      <header className="on-dark sticky top-0 z-30 bg-ink text-white">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
          {/* min-w-0 everywhere: on a 390px phone this row must never push the page wider. */}
          <div className="flex min-w-0 items-center gap-6">
            <Link href={HOME} className="flex min-w-0 items-center gap-2.5 text-subheading">
              <Logo size={24} className="shrink-0" />
              <span className="truncate">
                {t("app.name")}
                <span className="ml-1.5 hidden font-normal text-white/60 sm:inline">{t("nav.clinician")}</span>
              </span>
            </Link>
            {/* Phones use the bottom bar instead, which is what keeps this row from wrapping. */}
            <nav aria-label={t("nav.main")} className="hidden md:block">
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
          <div className="flex shrink-0 items-center gap-3">
            <span className="hidden max-w-[14rem] truncate text-small text-white/75 lg:block">
              {account.data?.name ?? session.user.email}
            </span>
            <Button variant="onDark" size="sm" onClick={logout}>
              <SignOut size={16} aria-hidden />
              <span className="max-sm:sr-only">{t("actions.signOut")}</span>
            </Button>
          </div>
        </div>
      </header>

      <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-4 pb-28 pt-6 sm:px-6 md:pb-8 lg:py-8">
        {children}
      </main>

      <footer className="border-t border-line bg-surface pb-20 md:pb-0">
        <p className="mx-auto max-w-7xl px-4 py-4 text-small text-muted sm:px-6">{t("nav.policy")}</p>
      </footer>

      {/* The phone bar the workspace never had: four destinations, thumb-reachable. */}
      <nav
        aria-label={t("nav.main")}
        className="on-dark fixed inset-x-0 bottom-0 z-30 bg-ink pb-[env(safe-area-inset-bottom)] md:hidden"
      >
        <ul className="mx-auto flex max-w-md items-stretch">
          {NAV.map(({ href, key, Icon }) => {
            const active = isActive(href);
            return (
              <li key={href} className="flex-1">
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex min-h-14 flex-col items-center justify-center gap-0.5 px-1 py-1.5 text-caption font-medium",
                    active ? "text-white" : "text-white/65",
                  )}
                >
                  <Icon size={22} weight={active ? "fill" : "regular"} />
                  <span className="leading-none">{t(key)}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
