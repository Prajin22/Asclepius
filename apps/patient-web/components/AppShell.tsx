"use client";

import { useAuth } from "@carebridge/api-client/react";
import { useT } from "@carebridge/i18n";
import { Button, LoadingState, Logo, cn } from "@carebridge/ui";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ComponentType, type ReactNode, type SVGProps } from "react";
import { ChatIcon, FileIcon, HeartIcon, HomeIcon, SearchIcon, UserIcon } from "./icons";
import { LanguageSwitcher } from "./LanguageSwitcher";

const NAV: { href: string; key: string; Icon: ComponentType<SVGProps<SVGSVGElement>> }[] = [
  { href: "/", key: "nav.dashboard", Icon: HomeIcon },
  { href: "/health", key: "nav.health", Icon: HeartIcon },
  { href: "/documents", key: "nav.documents", Icon: FileIcon },
  { href: "/consultations", key: "nav.consultations", Icon: ChatIcon },
  { href: "/find-care", key: "nav.findCare", Icon: SearchIcon },
  { href: "/profile", key: "nav.profile", Icon: UserIcon },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { session, ready, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const t = useT();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (ready && !session) router.replace("/login");
  }, [ready, session, router]);

  useEffect(() => setMenuOpen(false), [pathname]);

  if (!ready || !session) {
    return (
      <div className="mx-auto max-w-6xl px-4">
        <LoadingState />
      </div>
    );
  }

  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  const navList = (
    <ul className="flex flex-col gap-1">
      {NAV.map(({ href, key, Icon }) => (
        <li key={href}>
          <Link
            href={href}
            aria-current={isActive(href) ? "page" : undefined}
            className={cn(
              "flex min-h-12 items-center gap-3 rounded-lg px-3 font-medium transition-colors",
              isActive(href) ? "bg-brand-soft text-brand-strong" : "text-muted hover:bg-sunken hover:text-ink",
            )}
          >
            <Icon />
            {t(key)}
          </Link>
        </li>
      ))}
    </ul>
  );

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-4 focus:py-2"
      >
        {t("a11y.skipToContent")}
      </a>
      <header className="sticky top-0 z-20 border-b border-line bg-surface/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-2.5 text-lg font-semibold text-brand-strong">
            <Logo />
            {t("app.name")}
          </Link>
          <div className="flex items-center gap-2">
            <LanguageSwitcher />
            <Button variant="ghost" size="sm" className="hidden sm:inline-flex" onClick={logout}>
              {t("actions.signOut")}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              className="lg:hidden"
              aria-expanded={menuOpen}
              aria-controls="mobile-nav"
              onClick={() => setMenuOpen((v) => !v)}
            >
              {menuOpen ? t("nav.closeMenu") : t("nav.openMenu")}
            </Button>
          </div>
        </div>
        {menuOpen ? (
          <nav id="mobile-nav" aria-label={t("nav.main")} className="border-t border-line px-4 py-3 lg:hidden">
            {navList}
            <Button variant="ghost" className="mt-2 w-full justify-start sm:hidden" onClick={logout}>
              {t("actions.signOut")}
            </Button>
          </nav>
        ) : null}
      </header>

      <div className="mx-auto flex w-full max-w-6xl flex-1 gap-8 px-4 py-6 sm:px-6 lg:py-8">
        <nav aria-label={t("nav.main")} className="hidden w-56 shrink-0 lg:block">
          <div className="sticky top-24">{navList}</div>
        </nav>
        <main id="main" className="min-w-0 flex-1">
          {children}
        </main>
      </div>

      <footer className="border-t border-line bg-surface">
        <div className="mx-auto max-w-6xl px-4 py-5 text-sm text-muted sm:px-6">
          <p>{t("safety.notDiagnosis")}</p>
          <p className="mt-1 font-semibold text-danger">{t("safety.emergency")}</p>
        </div>
      </footer>
    </div>
  );
}
