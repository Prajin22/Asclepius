"use client";

import { useAuth } from "@carebridge/api-client/react";
import { I18nProvider, useT } from "@carebridge/i18n";
import { doctorCatalogs } from "@carebridge/i18n/catalogs";
import { Avatar, Button, LoadingState, Logo } from "@carebridge/ui";
import { SignOut } from "@phosphor-icons/react/dist/ssr";
import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { HOME_FOR_ROLE } from "@/lib/routes";

/** Administration is English in this prototype, like the clinician workspace. */
export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <I18nProvider locale="en" catalogs={doctorCatalogs}>
      <div lang="en">
        <AdminShell>{children}</AdminShell>
      </div>
    </I18nProvider>
  );
}

function AdminShell({ children }: { children: ReactNode }) {
  const { session, ready, logout } = useAuth();
  const router = useRouter();
  const t = useT();
  const isAdmin = session?.user.role === "admin";

  useEffect(() => {
    if (!ready) return;
    if (!session) router.replace("/login");
    else if (session.user.role !== "admin") router.replace(HOME_FOR_ROLE[session.user.role]);
  }, [ready, session, router]);

  if (!ready || !session || !isAdmin) {
    return (
      <div className="mx-auto max-w-6xl px-4">
        <LoadingState />
      </div>
    );
  }

  return (
    <div className="flex min-h-[100dvh] flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-3 focus:z-50 focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:shadow-md"
      >
        {t("a11y.skipToContent")}
      </a>
      <header className="sticky top-0 z-30 bg-ink text-white">
        <div className="mx-auto flex min-h-16 max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-2.5 sm:px-6">
          <p className="flex items-center gap-2.5 text-subheading tracking-tight">
            <Logo size={24} />
            <span>
              {t("app.name")}
              <span className="ml-1.5 font-normal text-white/60">{t("nav.admin")}</span>
            </span>
          </p>
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
      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 lg:py-8">
        {children}
      </main>
    </div>
  );
}
