"use client";

import { useAuth } from "@carebridge/api-client/react";
import { useT } from "@carebridge/i18n";
import { Avatar, Button, LoadingState, Logo, cn } from "@carebridge/ui";
import { SignOut } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

const NAV = [
  { href: "/", key: "nav.dashboard" },
  { href: "/profile", key: "nav.profile" },
];

/**
 * The clinician tool: ink chrome, dense content, no decoration. Same brand, same
 * type and colour system as the patient app — a different instrument.
 */
export function DoctorShell({ children }: { children: ReactNode }) {
  const { session, ready, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const t = useT();

  useEffect(() => {
    if (ready && !session) router.replace("/login");
  }, [ready, session, router]);

  if (!ready || !session) {
    return (
      <div className="mx-auto max-w-7xl px-4">
        <LoadingState />
      </div>
    );
  }

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" || pathname.startsWith("/cases") : pathname.startsWith(href);

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
            <Link href="/" className="flex items-center gap-2.5 text-subheading tracking-tight">
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
