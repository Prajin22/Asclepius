"use client";

import { useI18n } from "@carebridge/i18n";
import { Logo, ProvenanceBlock, ProvenanceChip, ReadingProvenance, buttonClasses, cn } from "@carebridge/ui";
import { ArrowDown, ArrowRight, FileText, Lock, ShieldCheck, Stethoscope } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import type { ReactNode } from "react";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { FoldScene } from "./FoldScene";

function Section({
  children,
  className,
  id,
  labelledBy,
}: {
  children: ReactNode;
  className?: string;
  id?: string;
  labelledBy?: string;
}) {
  return (
    <section id={id} aria-labelledby={labelledBy} className={cn("mx-auto w-full max-w-6xl px-5 sm:px-8", className)}>
      {children}
    </section>
  );
}

export function LandingPage() {
  const { t } = useI18n();

  // Five folds, and the numbers are the order the product works in.
  const steps = ["step1", "step2", "step3", "step4", "step5"] as const;

  const promises = [
    { key: "consent", Icon: ShieldCheck },
    { key: "original", Icon: Lock },
    { key: "decision", Icon: Stethoscope },
  ] as const;

  return (
    <div className="flex min-h-[100dvh] flex-col bg-canvas">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-3 focus:z-50 focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:shadow-md"
      >
        {t("a11y.skipToContent")}
      </a>

      <header className="sticky top-0 z-30 border-b border-line/70 bg-canvas/90 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-5 sm:px-8">
          <span className="flex items-center gap-2.5 text-subheading text-ink">
            <Logo size={26} className="text-brand" />
            {t("app.name")}
          </span>
          <div className="flex items-center gap-2">
            <LanguageSwitcher />
            <Link href="/login?role=doctor" className={buttonClasses("ghost", "sm", "max-sm:hidden")}>
              {t("landing.forDoctors")}
            </Link>
            <Link href="/login" className={buttonClasses("primary", "sm")}>
              {t("actions.signIn")}
            </Link>
          </div>
        </div>
      </header>

      <main id="main" className="flex-1">
        {/* Hero: one sheet, folding. The page's only colour field is the sheet itself. */}
        <Section className="grid items-center gap-10 py-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,28rem)] lg:gap-14 lg:py-20">
          <div className="max-w-2xl">
            <h1 className="text-display text-balance text-ink">{t("landing.hero.title")}</h1>
            <p className="mt-5 max-w-xl text-body-lg text-pretty text-muted">{t("landing.hero.subtitle")}</p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link href="/login" className={buttonClasses("primary", "lg")}>
                {t("landing.hero.primary")}
                <ArrowRight size={18} aria-hidden />
              </Link>
              <a href="#how" className={buttonClasses("secondary", "lg")}>
                {t("landing.hero.secondary")}
                <ArrowDown size={18} aria-hidden />
              </a>
            </div>
          </div>
          <figure className="m-0">
            <FoldScene className="relative mx-auto aspect-square w-full max-w-sm lg:max-w-none [&>canvas]:size-full" />
            <figcaption className="mt-3 text-center text-small text-subtle">{t("landing.sceneAlt")}</figcaption>
          </figure>
        </Section>

        {/* How it works: five folds, numbered, divided by creases rather than boxed in cards. */}
        <Section id="how" labelledBy="how-title" className="py-16 lg:py-24">
          <h2 id="how-title" className="max-w-2xl text-title text-balance text-ink">
            {t("landing.how.title")}
          </h2>
          <ol className="mt-10 divide-y divide-line border-y border-line">
            {steps.map((key, index) => (
              <li key={key} className="grid gap-x-6 gap-y-1 py-6 sm:grid-cols-[3rem_minmax(0,1fr)] lg:py-7">
                <span aria-hidden className="tabular text-step text-subtle">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div className="max-w-2xl">
                  <h3 className="text-subheading text-ink">{t(`landing.how.${key}.title`)}</h3>
                  <p className="mt-1 text-body text-pretty text-muted">{t(`landing.how.${key}.body`)}</p>
                </div>
              </li>
            ))}
          </ol>
        </Section>

        {/* Evidence, shown with the product's own components rather than a mock-up. */}
        <Section labelledBy="evidence-title" className="py-16 lg:py-24">
          <div className="grid gap-10 lg:grid-cols-2 lg:items-center lg:gap-16">
            <div>
              <h2 id="evidence-title" className="text-title text-balance text-ink">
                {t("landing.evidence.title")}
              </h2>
              <p className="mt-4 max-w-lg text-body-lg text-pretty text-muted">{t("landing.evidence.body")}</p>
            </div>
            <div className="flex flex-col gap-3">
              <ProvenanceBlock kind="original" lang="ta" meta="தமிழ்">
                <p className="text-body-lg">எனக்கு இரண்டு நாட்களாக தலைவலி மற்றும் காய்ச்சல் உள்ளது.</p>
              </ProvenanceBlock>
              <span className="flex justify-center">
                <ArrowDown size={20} aria-hidden className="text-subtle" />
              </span>
              <ProvenanceBlock kind="machine" meta={t("provenance.machineNote")}>
                <p>Patient reports headache and fever. Reported duration: 2 days.</p>
                <ul className="mt-3 flex flex-col gap-2">
                  {[
                    { value: "headache", quote: "தலைவலி" },
                    { value: "2 days", quote: "இரண்டு நாட்களாக" },
                  ].map((item) => (
                    <li key={item.value} className="rounded-md border border-ink/60 bg-surface px-3 py-2">
                      <span className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-semibold text-ink">{item.value}</span>
                        <ProvenanceChip kind="confirmed" />
                      </span>
                      <span className="mt-1 block text-small text-muted">
                        {t("ai.evidenceFrom")}: <q lang="ta">{item.quote}</q>
                      </span>
                    </li>
                  ))}
                </ul>
              </ProvenanceBlock>
            </div>
          </div>
        </Section>

        {/* Documents */}
        <Section labelledBy="documents-title" className="py-16 lg:py-24">
          <div className="grid gap-10 lg:grid-cols-2 lg:items-center lg:gap-16">
            <div className="order-2 flex flex-col gap-3 rounded-md border border-line bg-surface p-5 lg:order-1">
              <ReadingProvenance method="ocr" engine="rapidocr-onnxruntime 1.4.4" confidence={0.985} />
              <div className="rounded-md border border-paper-line bg-paper p-4 font-mono text-small leading-relaxed text-paper-ink">
                Demo Diagnostics Laboratory
                <br />
                Complete Blood Count
                <br />
                <mark className="rounded-sm bg-mark/40 px-1 text-paper-ink ring-1 ring-mark-ink">Hemoglobin: 13.5 g/dL</mark>
                <br />
                Blood pressure: 150/95 mmHg
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <ProvenanceChip kind="document" label="Page 1" />
                <span className="font-mono text-value text-ink">13.5 g/dL</span>
                <ProvenanceChip kind="machine" />
              </div>
            </div>
            <div className="order-1 lg:order-2">
              <h2 id="documents-title" className="text-title text-balance text-ink">
                {t("landing.documents.title")}
              </h2>
              <p className="mt-4 max-w-lg text-body-lg text-pretty text-muted">{t("landing.documents.body")}</p>
            </div>
          </div>
        </Section>

        {/* Languages */}
        <Section labelledBy="languages-title" className="py-16 lg:py-24">
          <div className="rounded-md border border-line bg-surface p-6 sm:p-10">
            <h2 id="languages-title" className="max-w-xl text-title text-balance text-ink">
              {t("landing.languages.title")}
            </h2>
            <p className="mt-4 max-w-xl text-body-lg text-pretty text-muted">{t("landing.languages.body")}</p>
            <ul className="mt-8 grid gap-4 sm:grid-cols-3">
              {[
                { lang: "ta", text: "மூன்று நாட்களாக தலைவலி" },
                { lang: "hi", text: "तीन दिन से सिरदर्द है" },
                { lang: "en", text: "Headache for three days" },
              ].map((sample) => (
                <li
                  key={sample.lang}
                  lang={sample.lang}
                  className="rounded-md border border-paper-line bg-paper px-4 py-3 text-body-lg text-paper-ink"
                >
                  {sample.text}
                </li>
              ))}
            </ul>
          </div>
        </Section>

        {/* The doctor's side: the page's one ink block, the clinician workspace's own material. */}
        <Section labelledBy="doctor-title" className="py-16 lg:py-24">
          <div className="on-dark overflow-hidden rounded-md bg-ink px-6 py-10 text-white sm:px-10 lg:px-14 lg:py-16">
            <div className="grid gap-8 lg:grid-cols-2 lg:items-center lg:gap-14">
              <div>
                <h2 id="doctor-title" className="text-title text-balance text-white">
                  {t("landing.doctor.title")}
                </h2>
                <p className="mt-4 max-w-lg text-body-lg text-pretty text-white/75">{t("landing.doctor.body")}</p>
              </div>
              <ul className="flex flex-col gap-3">
                {[
                  { icon: FileText, label: t("provenance.document"), body: t("landing.doctorView.documents") },
                  { icon: ShieldCheck, label: t("provenance.confirmed"), body: t("landing.doctorView.confirmed") },
                  { icon: Stethoscope, label: t("provenance.doctor"), body: t("landing.doctorView.assessment") },
                ].map(({ icon: Icon, label, body }) => (
                  <li key={label} className="flex items-start gap-3 rounded-md bg-white/[0.07] px-4 py-3">
                    <Icon size={20} weight="regular" aria-hidden className="mt-0.5 shrink-0 text-white/70" />
                    <span>
                      <span className="block font-semibold">{label}</span>
                      <span className="block text-small text-white/70">{body}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Section>

        {/* Trust: a statement and its three commitments, read as a list rather than three matching cards. */}
        <Section labelledBy="trust-title" className="py-16 lg:py-24">
          <div className="grid gap-8 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] lg:gap-16">
            <h2 id="trust-title" className="max-w-sm text-title text-balance text-ink">
              {t("landing.trust.title")}
            </h2>
            <ul className="divide-y divide-line border-y border-line">
              {promises.map(({ key, Icon }) => (
                <li key={key} className="flex items-start gap-4 py-5">
                  <span className="grid size-10 shrink-0 place-items-center rounded-md bg-brand-soft text-brand-strong">
                    <Icon size={20} weight="regular" aria-hidden />
                  </span>
                  <p className="pt-1.5 text-body-lg text-pretty text-ink">{t(`landing.trust.${key}`)}</p>
                </li>
              ))}
            </ul>
          </div>
        </Section>

        {/* Call to action: the one place the page is drenched in the sheet's own colour. */}
        <Section className="pb-20 pt-4 lg:pb-28">
          <div className="on-brand rounded-md bg-brand px-6 py-12 text-center text-white sm:px-10 lg:py-16">
            <h2 className="mx-auto max-w-2xl text-title text-balance text-white">{t("landing.cta.title")}</h2>
            <p className="mx-auto mt-3 max-w-md text-body text-white">{t("landing.cta.body")}</p>
            <Link
              href="/login"
              className={buttonClasses(
                "secondary",
                "lg",
                "mt-7 border-transparent bg-white text-brand-strong hover:bg-white hover:text-brand",
              )}
            >
              {t("landing.cta.action")}
              <ArrowRight size={18} aria-hidden />
            </Link>
          </div>
        </Section>
      </main>

      <footer className="border-t border-line bg-surface">
        <div className="mx-auto flex max-w-6xl flex-col gap-1 px-5 py-6 sm:px-8">
          <p className="text-small text-muted">{t("landing.footerNote")}</p>
          <p className="text-small font-semibold text-danger">{t("safety.emergency")}</p>
        </div>
      </footer>
    </div>
  );
}
