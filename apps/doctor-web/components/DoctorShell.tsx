"use client";

import { useAuth } from "@carebridge/api-client/react";
import { useT } from "@carebridge/i18n";
import { Button, LoadingState, Logo, cn } from "@carebridge/ui";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

const NAV = [
  { href: "/", key: "nav.dashboard" },
  { href: "/profile", key: "nav.profile" },
];

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

  const isActive = (href: string) => (href === "/" ? pathname === "/" || pathname.startsWith("/cases") : pathname.startsWith(href));

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-4 focus:py-2"
      >
        {t("a11y.skipToContent")}
      </a>
      <header className="sticky top-0 z-20 bg-brand-strong text-white">
        <div className="mx-auto flex min-h-14 max-w-7xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-2 sm:px-6">
          <div className="flex items-center gap-6">
            <Link href="/" className="flex items-center gap-2.5 font-semibold">
              <Logo size={26} />
              <span>
                {t("app.name")} <span className="font-normal text-white/70">· {t("nav.clinician")}</span>
              </span>
            </Link>
            <nav aria-label={t("nav.main")}>
              <ul className="flex gap-1">
                {NAV.map((item) => (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      aria-current={isActive(item.href) ? "page" : undefined}
                      className={cn(
                        "inline-flex min-h-10 items-center rounded-md px-3 text-sm font-medium",
                        isActive(item.href) ? "bg-white/15 text-white" : "text-white/80 hover:bg-white/10 hover:text-white",
                      )}
                    >
                      {t(item.key)}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="hidden text-white/80 md:inline">{session.user.email}</span>
            <Button variant="secondary" size="sm" onClick={logout}>
              {t("actions.signOut")}
            </Button>
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">
        {children}
      </main>
      <footer className="border-t border-line bg-surface">
        <p className="mx-auto max-w-7xl px-4 py-4 text-sm text-muted sm:px-6">{t("nav.policy")}</p>
      </footer>
    </div>
  );
}
