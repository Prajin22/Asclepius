"use client";

import { useT } from "@carebridge/i18n";
import { Alert, Badge, buttonClasses } from "@carebridge/ui";
import Link from "next/link";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { SAKTI_NAV } from "./nav";
import { SaktiMark } from "./SaktiMark";

/**
 * The public front door of IP-SAKTI Sahayak. It says what the product is for,
 * that it is not built yet, and that it is not legal advice — and promises
 * nothing the product cannot yet do.
 */
export function SaktiLanding() {
  const t = useT();
  return (
    <div className="flex min-h-[100dvh] flex-col">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
          <span className="min-w-0">
            <SaktiMark className="max-sm:hidden" />
            <SaktiMark compact className="sm:hidden" />
          </span>
          <div className="flex shrink-0 items-center gap-2">
            <LanguageSwitcher />
            <Link href="/login" className={buttonClasses("primary", "sm", "whitespace-nowrap")}>
              {t("actions.signIn")}
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-12 sm:px-6 lg:py-20">
        <div className="grid gap-12 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:items-start">
          <section>
            <h1 className="text-title text-balance text-ink">{t("app.name")}</h1>
            <p className="mt-3 max-w-[38ch] text-heading font-normal text-brand-strong">{t("app.domain")}</p>
            <p className="mt-6 max-w-[62ch] text-body-lg text-muted">{t("landing.lead")}</p>
            <Alert tone="info" className="mt-8 max-w-[62ch]">
              {t("landing.status")}
            </Alert>
            <Link href="/login" className={buttonClasses("primary", "md", "mt-8")}>
              {t("actions.signIn")}
            </Link>
          </section>

          <section aria-labelledby="areas" className="rounded-lg border border-line bg-surface p-6">
            <h2 id="areas" className="text-subheading text-ink">
              {t("landing.areasTitle")}
            </h2>
            <ul className="mt-4 flex flex-col divide-y divide-line">
              {SAKTI_NAV.user.map(({ page, label, Icon }) => (
                <li key={page} className="flex gap-3 py-4 first:pt-0 last:pb-0">
                  <Icon size={22} className="mt-0.5 shrink-0 text-brand" aria-hidden />
                  <div className="min-w-0">
                    <p className="flex flex-wrap items-center gap-2 font-semibold text-ink">
                      {t(label)}
                      <Badge tone="neutral">{t("notAvailable.badge")}</Badge>
                    </p>
                    <p className="mt-0.5 text-small text-muted">{t(`pages.${page}.description`)}</p>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </main>

      <footer className="border-t border-line bg-surface">
        <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
          <p className="text-small text-muted">{t("disclaimer.short")}</p>
          <p className="mt-1 text-caption text-subtle">{t("disclaimer.prototype")}</p>
        </div>
      </footer>
    </div>
  );
}
