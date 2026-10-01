"use client";

import { useAuth } from "@carebridge/api-client/react";
import { useT } from "@carebridge/i18n";
import type { SaktiRole } from "@carebridge/shared-types";
import { Button, LoadingState, cn } from "@carebridge/ui";
import { SignOut } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { acceptsRole } from "@/lib/product";
import { HOME_FOR_ROLE } from "@/lib/routes";
import { SAKTI_NAV } from "./nav";
import { SaktiMark } from "./SaktiMark";

/**
 * The IP-SAKTI Sahayak shell, one per role: the user's four destinations, the
 * facilitator's desk, the curator's corpus, the administrator's facilitators.
 *
 * The disclaimer is part of the chrome, on every screen, not a footnote on
 * some of them. The API refuses anything a role may not do; this shell only
 * sends each role to its own area.
 */
export function SaktiShell({ role, children }: { role: SaktiRole; children: ReactNode }) {
  const { session, ready, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const t = useT();
  const allowed = session?.user.role === role;

  useEffect(() => {
    if (!ready) return;
    if (!session) router.replace("/login");
    else if (!acceptsRole(session.user.role, "ip_sakti")) {
      // A session from the other product can only come from tampering with storage.
      logout();
      router.replace("/login");
    } else if (session.user.role !== role) router.replace(HOME_FOR_ROLE[session.user.role]);
  }, [ready, session, role, router, logout]);

  if (!ready || !session || !allowed) {
    return (
      <div className="mx-auto max-w-6xl px-4">
        <LoadingState />
      </div>
    );
  }

  const nav = SAKTI_NAV[role];
  const home = nav[0].href;
  const isActive = (href: string) => (href === home ? pathname === home : pathname.startsWith(href));

  return (
    <div className="flex min-h-[100dvh] flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-3 focus:z-50 focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:shadow-md"
      >
        {t("a11y.skipToContent")}
      </a>

      <header className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <Link href={home} aria-label={t("app.name")} className="shrink-0">
              <SaktiMark className="max-sm:hidden" />
              <SaktiMark compact className="sm:hidden" />
            </Link>
            {role === "user" ? null : (
              <span className="truncate border-l border-line pl-3 text-small font-medium text-muted max-sm:hidden">
                {t(`areaLabel.${role}`)}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <LanguageSwitcher />
            <Button variant="ghost" size="sm" onClick={logout} className="max-sm:px-2.5">
              <SignOut size={18} aria-hidden />
              <span className="max-sm:sr-only">{t("actions.signOut")}</span>
            </Button>
          </div>
        </div>
      </header>

      <div
        className={cn(
          "mx-auto flex w-full max-w-6xl flex-1 gap-8 px-4 pt-5 sm:px-6 lg:pb-12 lg:pt-8",
          nav.length > 1 ? "pb-28" : "pb-10",
        )}
      >
        <nav aria-label={t("nav.main")} className="hidden w-60 shrink-0 lg:block">
          <div className="sticky top-24 flex flex-col gap-6">
            <ul className="flex flex-col gap-1">
              {nav.map(({ href, label, Icon }) => {
                const active = isActive(href);
                return (
                  <li key={href}>
                    <Link
                      href={href}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex min-h-11 items-center gap-3 rounded-md px-3 font-medium transition-colors duration-150",
                        active ? "bg-brand text-white" : "text-muted hover:bg-sunken hover:text-ink",
                      )}
                    >
                      <Icon weight={active ? "fill" : "regular"} />
                      {t(label)}
                    </Link>
                  </li>
                );
              })}
            </ul>
            <p className="border-t border-line pt-4 text-caption leading-relaxed text-subtle">{t("disclaimer.short")}</p>
          </div>
        </nav>

        <main id="main" className="min-w-0 flex-1">
          {/* On a phone the header has no room for the area's name; it goes here. */}
          {role === "user" ? null : (
            <p className="mb-2 text-small font-medium text-muted sm:hidden">{t(`areaLabel.${role}`)}</p>
          )}
          {children}
        </main>
      </div>

      <footer className={cn("border-t border-line bg-surface", nav.length > 1 ? "pb-20 lg:pb-0" : undefined)}>
        <div className="mx-auto max-w-6xl px-4 py-5 sm:px-6">
          <p className="text-small text-muted lg:hidden">{t("disclaimer.short")}</p>
          <p className="mt-1 text-caption text-subtle lg:mt-0">{t("disclaimer.prototype")}</p>
        </div>
      </footer>

      {/* One destination needs no bar. */}
      {nav.length > 1 ? (
        <nav
          aria-label={t("nav.main")}
          className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md lg:hidden"
        >
          <ul className="mx-auto flex max-w-md items-stretch">
            {nav.map(({ href, label, Icon }) => {
              const active = isActive(href);
              return (
                <li key={href} className="flex-1">
                  <Link
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex min-h-14 flex-col items-center justify-center gap-0.5 px-1 py-1.5 text-center text-caption font-medium leading-tight transition-colors duration-150",
                      active ? "text-brand-strong" : "text-muted",
                    )}
                  >
                    <Icon size={22} weight={active ? "fill" : "regular"} />
                    <span>{t(label)}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      ) : null}
    </div>
  );
}
