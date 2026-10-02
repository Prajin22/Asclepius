"use client";

import { useT } from "@carebridge/i18n";
import { Badge, buttonClasses, type Tone } from "@carebridge/ui";
import { ArrowRight, CheckCircle, Clock, Info, UserCircleGear } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { AskIcon, ClassifyIcon, CorpusIcon, EscalateIcon, ProductIcon } from "@/components/icons";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { SaktiMark } from "./SaktiMark";
import { LaneMark } from "./ui";

type Availability = "available" | "curators" | "later";

const CAPABILITIES: { key: string; Icon: typeof AskIcon; status: Availability }[] = [
  { key: "profiles", Icon: ProductIcon, status: "available" },
  { key: "classifier", Icon: ClassifyIcon, status: "available" },
  { key: "corpus", Icon: CorpusIcon, status: "curators" },
  { key: "answers", Icon: AskIcon, status: "later" },
  { key: "escalation", Icon: EscalateIcon, status: "later" },
];

const STATUS: Record<Availability, { tone: Tone; icon: typeof CheckCircle }> = {
  available: { tone: "success", icon: CheckCircle },
  curators: { tone: "info", icon: UserCircleGear },
  later: { tone: "neutral", icon: Clock },
};

/**
 * The public front door of IP-SAKTI Sahayak. It says what the product is for,
 * exactly what works today and what does not yet, and that it is information
 * only — not legal advice, and not an official service. It promises nothing
 * the product cannot do, and links nowhere but sign-in.
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

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-12 sm:px-6 lg:py-16">
        <div className="grid gap-10 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:items-start">
          <section>
            <p className="text-label uppercase text-brand-strong">{t("landing.eyebrow")}</p>
            <h1 className="mt-4 text-display text-balance text-ink">{t("app.name")}</h1>
            <p className="mt-4 max-w-[38ch] text-heading font-normal text-brand-strong">{t("app.domain")}</p>
            <p className="mt-6 max-w-[62ch] text-body-lg text-muted">{t("landing.lead")}</p>
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <Link href="/login" className={buttonClasses("primary", "lg")}>
                {t("actions.signIn")}
                <ArrowRight size={18} aria-hidden />
              </Link>
              <p className="flex max-w-xs items-start gap-2 text-small text-muted">
                <Info size={16} aria-hidden className="mt-0.5 shrink-0" />
                {t("ui.infoOnly")}
              </p>
            </div>
          </section>

          <section aria-labelledby="principles" className="rounded-md border border-line bg-surface p-6">
            <h2 id="principles" className="text-subheading text-ink">
              {t("landing.principles.title")}
            </h2>
            <ol className="mt-4 flex flex-col gap-4">
              {(["sources", "lanes", "abstain"] as const).map((k, i) => (
                <li key={k} className="flex gap-3">
                  <span aria-hidden className="grid size-7 shrink-0 place-items-center rounded-full bg-brand-soft text-small font-bold text-brand-strong">
                    {i + 1}
                  </span>
                  <div className="min-w-0">
                    <p className="font-semibold text-ink">{t(`landing.principles.${k}.title`)}</p>
                    <p className="text-small text-muted">{t(`landing.principles.${k}.body`)}</p>
                    {k === "lanes" ? (
                      <p className="mt-2 flex flex-wrap gap-2">
                        <LaneMark lane="india" size="sm" />
                        <LaneMark lane="international" size="sm" />
                      </p>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </div>

        <section aria-labelledby="areas" className="mt-14">
          <h2 id="areas" className="text-heading text-ink">
            {t("landing.areasTitle")}
          </h2>
          <p className="mt-1 max-w-[62ch] text-muted">{t("landing.status")}</p>
          <ul className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {CAPABILITIES.map(({ key, Icon, status }) => {
              const { tone, icon: Glyph } = STATUS[status];
              return (
                <li key={key} className="flex flex-col gap-3 rounded-md border border-line bg-surface p-5">
                  <div className="flex items-start justify-between gap-3">
                    <span className="grid size-10 place-items-center rounded-md bg-brand-tint text-brand">
                      <Icon size={22} aria-hidden />
                    </span>
                    <Badge tone={tone}>
                      <Glyph size={13} weight="bold" aria-hidden />
                      {t(`landing.availability.${status}`)}
                    </Badge>
                  </div>
                  <div>
                    <p className="font-semibold text-ink">{t(`landing.capabilities.${key}.title`)}</p>
                    <p className="mt-0.5 text-small text-muted">{t(`landing.capabilities.${key}.body`)}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
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
