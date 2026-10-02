"use client";

import { useAuth, useQuery } from "@carebridge/api-client/react";
import { useT } from "@carebridge/i18n";
import type { SaktiRole } from "@carebridge/shared-types";
import { Avatar, LoadingState, Sheet, cn } from "@carebridge/ui";
import { CaretDown, Clock, List, SignOut } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { acceptsRole } from "@/lib/product";
import { HOME_FOR_ROLE } from "@/lib/routes";
import { SAKTI_NAV, SAKTI_PAGES, type SaktiNavItem } from "./nav";
import { SaktiMark } from "./SaktiMark";
import { DemoTag } from "./ui";

/** Whether the API runs in demo mode (synthetic accounts and data). False until known. */
const DemoModeContext = createContext(false);
export const useDemoMode = () => useContext(DemoModeContext);
/** Supplies demo mode outside the shell — for screens rendered on their own, as in tests. */
export const DemoModeProvider = DemoModeContext.Provider;

/**
 * The IP-SAKTI Sahayak shell, one per role: the user's workspace, the
 * facilitator's desk, the curator's corpus, the administrator's facilitators.
 *
 * Desktop: a persistent sidebar with the role's destinations. Phone and
 * tablet: a compact header whose menu opens the same destinations in a sheet.
 * The disclaimer is part of the chrome on every screen. In demo mode a "Demo
 * data" marker sits in the header on every screen and explains itself.
 *
 * The API refuses anything a role may not do; this shell only sends each role
 * to its own area.
 */
export function SaktiShell({ role, children }: { role: SaktiRole; children: ReactNode }) {
  const { session, ready, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const t = useT();
  const allowed = session?.user.role === role;
  const meta = useQuery((a) => a.meta.product());
  const demo = meta.data?.demo_mode === true;
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!ready) return;
    if (!session) router.replace("/login");
    else if (!acceptsRole(session.user.role, "ip_sakti")) {
      // A session from the other product can only come from tampering with storage.
      logout();
      router.replace("/login");
    } else if (session.user.role !== role) router.replace(HOME_FOR_ROLE[session.user.role]);
  }, [ready, session, role, router, logout]);

  // A destination chosen from the menu closes it.
  useEffect(() => setMenuOpen(false), [pathname]);

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
    <DemoModeContext.Provider value={demo}>
      <div className="min-h-[100dvh] lg:grid lg:grid-cols-[16.5rem_minmax(0,1fr)]">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-3 focus:z-50 focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:shadow-md"
        >
          {t("a11y.skipToContent")}
        </a>

        {/* The column carries the surface the full height of the page; the sidebar inside it stays in view. */}
        <div className="hidden border-r border-line bg-surface lg:block">
          <aside className="sticky top-0 flex h-[100dvh] flex-col">
            <div className="flex h-16 shrink-0 items-center border-b border-line px-5">
              <Link href={home} aria-label={t("app.name")} className="rounded-md">
                <SaktiMark />
              </Link>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-3 py-5">
              <p className="px-3 pb-3 text-label uppercase text-subtle">{t(`areaLabel.${role}`)}</p>
              <NavList items={nav} isActive={isActive} label={t("nav.main")} />
            </div>
            <p className="shrink-0 border-t border-line px-5 py-4 text-caption leading-relaxed text-subtle">
              {t("disclaimer.short")}
            </p>
          </aside>
        </div>

        <div className="flex min-h-[100dvh] min-w-0 flex-col">
          <header className="sticky top-0 z-30 border-b border-line bg-surface">
            <div className="flex h-16 items-center justify-between gap-2 px-3 sm:px-6 lg:px-8">
              <div className="flex min-w-0 items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => setMenuOpen(true)}
                  aria-label={t("ui.shell.openMenu")}
                  aria-expanded={menuOpen}
                  className="grid size-11 shrink-0 place-items-center rounded-md text-ink hover:bg-sunken lg:hidden"
                >
                  <List size={22} aria-hidden />
                </button>
                <Link href={home} aria-label={t("app.name")} className="shrink-0 rounded-md lg:hidden">
                  {/* Full name, short name, or just the square: whichever fits beside the header's controls. */}
                  <span className="hidden sm:inline">
                    <SaktiMark />
                  </span>
                  <span className="hidden min-[400px]:inline sm:hidden">
                    <SaktiMark compact />
                  </span>
                  <span className="min-[400px]:hidden">
                    <SaktiMark iconOnly />
                  </span>
                </Link>
                <p className="hidden truncate text-small font-medium text-muted lg:block">{t(`areaLabel.${role}`)}</p>
              </div>
              <div className="flex shrink-0 items-center gap-1.5 sm:gap-2.5">
                {demo ? <DemoChip /> : null}
                <LanguageSwitcher />
                <UserMenu email={session.user.email} role={role} onSignOut={logout} />
              </div>
            </div>
          </header>

          <main id="main" className="flex-1 px-4 pb-12 pt-6 sm:px-6 lg:px-10 lg:pt-8">
            <div className="mx-auto w-full max-w-6xl">{children}</div>
          </main>

          <footer className="border-t border-line bg-surface">
            <div className="mx-auto max-w-6xl px-4 py-5 sm:px-6 lg:px-10">
              <p className="text-small text-muted lg:hidden">{t("disclaimer.short")}</p>
              <p className="mt-1 text-caption text-subtle lg:mt-0">{t("disclaimer.prototype")}</p>
            </div>
          </footer>
        </div>

        <Sheet open={menuOpen} onClose={() => setMenuOpen(false)} title={t("app.name")} description={t(`areaLabel.${role}`)}>
          <NavList items={nav} isActive={isActive} label={t("nav.main")} />
          <p className="mt-5 border-t border-line pt-4 text-caption leading-relaxed text-subtle">{t("disclaimer.short")}</p>
        </Sheet>
      </div>
    </DemoModeContext.Provider>
  );
}

/** The role's destinations, grouped. A screen whose capability does not exist yet says so. */
function NavList({ items, isActive, label }: { items: readonly SaktiNavItem[]; isActive: (href: string) => boolean; label: string }) {
  const t = useT();
  return (
    <nav aria-label={label}>
      <ul className="flex flex-col gap-0.5">
        {items.map(({ href, label: key, Icon, group, page }) => {
          const active = isActive(href);
          const later = !SAKTI_PAGES[page].available;
          return (
            <li key={href}>
              {group ? <p className="px-3 pb-1.5 pt-4 text-label uppercase text-subtle">{t(group)}</p> : null}
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "relative flex min-h-11 items-center gap-3 rounded-md px-3 font-medium transition-colors duration-150",
                  active
                    ? "bg-brand-soft text-brand-strong before:absolute before:inset-y-2 before:left-0 before:w-[3px] before:rounded-full before:bg-brand"
                    : "text-muted hover:bg-sunken hover:text-ink",
                )}
              >
                <Icon weight={active ? "fill" : "regular"} />
                <span className="min-w-0 flex-1">{t(key)}</span>
                {later ? (
                  <span className="inline-flex shrink-0 items-center gap-1 text-caption font-medium text-subtle">
                    <Clock size={13} aria-hidden />
                    {t("nav.later")}
                  </span>
                ) : null}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** "Demo data", always visible in demo mode. Pressing it says exactly what is synthetic and what is not. */
function DemoChip() {
  const t = useT();
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        className="rounded-sm"
        aria-label={t("ui.demo.explain")}
      >
        <DemoTag className="max-sm:hidden" />
        <DemoTag className="sm:hidden" label={t("ui.demo.short")} />
      </button>
      <Sheet open={open} onClose={() => setOpen(false)} title={t("ui.demo.title")}>
        <div className="flex flex-col gap-3 text-ink">
          <p>{t("ui.demo.body")}</p>
          <ul className="flex list-disc flex-col gap-1.5 pl-5 text-small marker:text-demo">
            <li>{t("ui.demo.points.accounts")}</li>
            <li>{t("ui.demo.points.samples")}</li>
            <li>{t("ui.demo.points.never")}</li>
          </ul>
        </div>
      </Sheet>
    </>
  );
}

/** The signed-in account: who, which role, and signing out. A disclosure, closed by Escape or a click outside. */
function UserMenu({ email, role, onSignOut }: { email: string; role: SaktiRole; onSignOut: () => void }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        button.current?.focus();
      }
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={box} className="relative">
      <button
        ref={button}
        type="button"
        aria-expanded={open}
        aria-controls={id}
        aria-label={t("ui.user.menu")}
        onClick={() => setOpen((v) => !v)}
        className="flex min-h-11 items-center gap-2 rounded-md px-1.5 text-small font-medium text-ink hover:bg-sunken sm:min-h-10"
      >
        <Avatar name={email} size="sm" />
        <span className="hidden max-w-[12rem] truncate xl:block">{email}</span>
        <CaretDown size={14} aria-hidden className="max-sm:hidden" />
      </button>
      {open ? (
        <div
          id={id}
          className="absolute right-0 top-full z-40 mt-2 w-72 max-w-[calc(100vw-1.5rem)] rounded-md border border-line bg-surface p-1.5 shadow-lg motion-safe:animate-rise"
        >
          <div className="border-b border-line px-3 pb-3 pt-2">
            <p className="text-caption text-subtle">{t("ui.user.signedInAs")}</p>
            <p className="truncate font-medium text-ink">{email}</p>
            <p className="mt-0.5 text-small text-muted">{t(`role.${role}`)}</p>
          </div>
          <button
            type="button"
            onClick={onSignOut}
            className="mt-1 flex min-h-11 w-full items-center gap-2.5 rounded-sm px-3 text-left font-medium text-ink hover:bg-sunken"
          >
            <SignOut size={18} aria-hidden />
            {t("actions.signOut")}
          </button>
        </div>
      ) : null}
    </div>
  );
}
