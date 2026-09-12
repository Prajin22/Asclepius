"use client";

import { useAuth } from "@carebridge/api-client/react";
import { useT } from "@carebridge/i18n";
import { Button, LoadingState, Logo, buttonClasses, cn } from "@carebridge/ui";
import { SignOut } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ComponentProps, type ReactNode } from "react";
import { ChatIcon, FileIcon, HeartIcon, HomeIcon, SearchIcon, UserIcon } from "./icons";
import { LanguageSwitcher } from "./LanguageSwitcher";

type NavIcon = (props: ComponentProps<typeof HomeIcon>) => ReactNode;

/** Five destinations, so the bar stays inside one thumb's reach. */
const NAV: { href: string; key: string; Icon: NavIcon }[] = [
  { href: "/home", key: "nav.dashboard", Icon: HomeIcon },
  { href: "/health", key: "nav.health", Icon: HeartIcon },
  { href: "/documents", key: "nav.documents", Icon: FileIcon },
  { href: "/consultations", key: "nav.consultations", Icon: ChatIcon },
  { href: "/profile", key: "nav.profile", Icon: UserIcon },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { session, ready, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const t = useT();

  useEffect(() => {
    if (ready && !session) router.replace("/login");
  }, [ready, session, router]);

  if (!ready || !session) {
    return (
      <div className="mx-auto max-w-6xl px-4">
        <LoadingState />
      </div>
    );
  }

  const isActive = (href: string) => (href === "/home" ? pathname === "/home" : pathname.startsWith(href));

  return (
    <div className="flex min-h-[100dvh] flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-4 focus:py-2 focus:shadow-md"
      >
        {t("a11y.skipToContent")}
      </a>

      <header className="sticky top-0 z-30 border-b border-line bg-surface/90 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
          <Link
            href="/home"
            className="flex items-center gap-2.5 text-subheading tracking-tight text-brand-strong"
            aria-label={t("app.name")}
          >
            <Logo size={26} />
            <span>{t("app.name")}</span>
          </Link>
          <div className="flex items-center gap-2">
            <LanguageSwitcher />
            <Button variant="ghost" size="sm" onClick={logout} className="max-sm:px-2.5">
              <SignOut size={18} aria-hidden />
              <span className="max-sm:sr-only">{t("actions.signOut")}</span>
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-6xl flex-1 gap-8 px-4 pb-28 pt-5 sm:px-6 lg:pb-12 lg:pt-8">
        {/* Desktop rail. On a phone this is the bottom bar instead. */}
        <nav aria-label={t("nav.main")} className="hidden w-60 shrink-0 lg:block">
          <div className="sticky top-24 flex flex-col gap-6">
            <ul className="flex flex-col gap-1">
              {NAV.map(({ href, key, Icon }) => {
                const active = isActive(href);
                return (
                  <li key={href}>
                    <Link
                      href={href}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex min-h-11 items-center gap-3 rounded-md px-3 font-medium transition-colors duration-150",
                        active ? "bg-brand-soft text-brand-strong" : "text-muted hover:bg-sunken hover:text-ink",
                      )}
                    >
                      <Icon weight={active ? "fill" : "regular"} />
                      {t(key)}
                    </Link>
                  </li>
                );
              })}
            </ul>
            <Link href="/find-care" className={buttonClasses("primary", "md", "w-full")}>
              <SearchIcon size={18} />
              {t("findCare.title")}
            </Link>
            <p className="text-caption leading-relaxed text-subtle">{t("safety.notDiagnosis")}</p>
          </div>
        </nav>

        <main id="main" className="min-w-0 flex-1">
          {children}
        </main>
      </div>

      <footer className="border-t border-line bg-surface pb-20 lg:pb-0">
        <div className="mx-auto max-w-6xl px-4 py-5 sm:px-6">
          <p className="text-small text-muted lg:hidden">{t("safety.notDiagnosis")}</p>
          <p className="mt-1 text-small font-semibold text-danger lg:mt-0">{t("safety.emergency")}</p>
        </div>
      </footer>

      {/* Bottom bar: thumb-reachable, labelled, and out of the way on desktop. */}
      <nav
        aria-label={t("nav.main")}
        className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md lg:hidden"
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
                    "flex min-h-14 flex-col items-center justify-center gap-0.5 px-1 py-1.5 text-caption font-medium transition-colors duration-150",
                    active ? "text-brand-strong" : "text-muted",
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
