"use client";

import { useI18n } from "@carebridge/i18n";
import {
  Logo,
  ProvenanceBlock,
  ProvenanceChip,
  ReadingProvenance,
  buttonClasses,
  cn,
} from "@carebridge/ui";
import { ArrowDown, ArrowRight, FileText, Lock, ShieldCheck, Stethoscope } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useEffect, useRef, type ReactNode } from "react";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { HelixScene } from "./HelixScene";

/**
 * Sections arrive as the reader reaches them — the only motion on the page, and
 * only when the reader has not asked for less of it. Without JavaScript, or with
 * reduced motion, everything is simply already there.
 */
function useReveal() {
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    // Strict Mode mounts effects twice, and the cleanup runs before this dynamic
    // import resolves — so a late arrival must not build a second set of tweens
    // on top of the first. Two overlapping `from` tweens would capture the
    // already-hidden state as the end state and leave the page blank.
    let cancelled = false;
    let context: { revert: () => void } | undefined;
    void (async () => {
      const [{ gsap }, { ScrollTrigger }] = await Promise.all([import("gsap"), import("gsap/ScrollTrigger")]);
      if (cancelled) return;
      gsap.registerPlugin(ScrollTrigger);
      context = gsap.context(() => {
        gsap.utils.toArray<HTMLElement>("[data-reveal]").forEach((element) => {
          // fromTo, not from: the visible end state is stated outright, so it can
          // never be inferred from whatever the element happens to look like now.
          gsap.fromTo(
            element,
            { opacity: 0, y: 20 },
            {
              opacity: 1,
              y: 0,
              duration: 0.65,
              ease: "power2.out",
              overwrite: "auto",
              scrollTrigger: { trigger: element, start: "top 88%", once: true },
            },
          );
        });
      }, root);
      // Webfonts swap in after the triggers are measured and shift everything
      // down; re-measure once they have settled.
      void document.fonts?.ready.then(() => {
        if (!cancelled) ScrollTrigger.refresh();
      });
    })();
    return () => {
      cancelled = true;
      context?.revert();
    };
  }, []);
  return root;
}

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
  const root = useReveal();

  const steps = [
    { key: "step1", n: "01" },
    { key: "step2", n: "02" },
    { key: "step3", n: "03" },
  ] as const;

  const promises = [
    { key: "consent", Icon: ShieldCheck },
    { key: "original", Icon: Lock },
    { key: "decision", Icon: Stethoscope },
  ] as const;

  return (
    <div ref={root} className="flex min-h-[100dvh] flex-col bg-canvas">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-4 focus:py-2 focus:shadow-md"
      >
        {t("a11y.skipToContent")}
      </a>

      <header className="sticky top-0 z-30 border-b border-line/70 bg-canvas/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-5 sm:px-8">
          <span className="flex items-center gap-2.5 text-subheading tracking-tight text-brand-strong">
            <Logo size={26} />
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
        {/* Hero */}
        <Section className="grid items-center gap-10 py-12 lg:min-h-[calc(100dvh-4rem)] lg:grid-cols-[minmax(0,1fr)_minmax(0,30rem)] lg:gap-14 lg:py-16">
          <div className="max-w-2xl">
            <h1 className="text-display text-balance text-ink">{t("landing.hero.title")}</h1>
            <p className="mt-5 max-w-xl text-body-lg text-muted">{t("landing.hero.subtitle")}</p>
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
          <HelixScene className="relative mx-auto aspect-[4/5] w-full max-w-sm lg:max-w-none [&>canvas]:size-full" />
        </Section>

        {/* How it works */}
        <Section id="how" labelledBy="how-title" className="py-16 lg:py-24">
          <h2 id="how-title" data-reveal className="max-w-2xl text-title text-ink">
            {t("landing.how.title")}
          </h2>
          <ol className="mt-10 grid gap-px overflow-hidden rounded-xl border border-line bg-line md:grid-cols-3">
            {steps.map(({ key, n }) => (
              <li key={key} data-reveal className="flex flex-col gap-3 bg-surface p-6 lg:p-8">
                <span className="text-label uppercase tabular text-brand">{n}</span>
                <h3 className="text-subheading text-ink">{t(`landing.how.${key}.title`)}</h3>
                <p className="text-body text-muted">{t(`landing.how.${key}.body`)}</p>
              </li>
            ))}
          </ol>
        </Section>

        {/* Evidence — shown with the product's own components, not a mock-up. */}
        <Section labelledBy="evidence-title" className="py-16 lg:py-24">
          <div className="grid gap-10 lg:grid-cols-2 lg:items-center lg:gap-16">
            <div data-reveal>
              <h2 id="evidence-title" className="text-title text-balance text-ink">
                {t("landing.evidence.title")}
              </h2>
              <p className="mt-4 max-w-lg text-body-lg text-muted">{t("landing.evidence.body")}</p>
            </div>
            <div data-reveal className="flex flex-col gap-3">
              <ProvenanceBlock kind="original" lang="ta" meta="தமிழ்">
                <p className="text-body-lg">எனக்கு இரண்டு நாட்களாக தலைவலி மற்றும் காய்ச்சல் உள்ளது.</p>
              </ProvenanceBlock>
              <ArrowDown size={20} aria-hidden className="mx-auto text-subtle" />
              <ProvenanceBlock kind="machine" meta={t("provenance.machineNote")}>
                <p>Patient reports headache and fever. Reported duration: 2 days.</p>
                <ul className="mt-3 flex flex-col gap-2">
                  {[
                    { value: "headache", quote: "தலைவலி" },
                    { value: "2 days", quote: "இரண்டு நாட்களாக" },
                  ].map((item) => (
                    <li key={item.value} className="rounded-md border border-ai-line/70 bg-surface px-3 py-2">
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
            <div data-reveal className="order-2 flex flex-col gap-3 rounded-xl border border-line bg-surface p-5 lg:order-1">
              <ReadingProvenance method="ocr" engine="rapidocr-onnxruntime 1.4.4" confidence={0.985} />
              <div className="rounded-lg border border-paper-line bg-paper p-4 font-mono text-small leading-relaxed text-paper-ink">
                Demo Diagnostics Laboratory
                <br />
                Complete Blood Count
                <br />
                <mark className="rounded-sm bg-brand-soft px-1 text-brand-strong">Hemoglobin: 13.5 g/dL</mark>
                <br />
                Blood pressure: 150/95 mmHg
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <ProvenanceChip kind="document" label="Page 1" />
                <span className="text-value font-mono text-ink">13.5 g/dL</span>
                <ProvenanceChip kind="machine" />
              </div>
            </div>
            <div data-reveal className="order-1 lg:order-2">
              <h2 id="documents-title" className="text-title text-balance text-ink">
                {t("landing.documents.title")}
              </h2>
              <p className="mt-4 max-w-lg text-body-lg text-muted">{t("landing.documents.body")}</p>
            </div>
          </div>
        </Section>

        {/* Languages */}
        <Section labelledBy="languages-title" className="py-16 lg:py-24">
          <div data-reveal className="rounded-2xl border border-line bg-surface p-6 sm:p-10">
            <h2 id="languages-title" className="max-w-xl text-title text-balance text-ink">
              {t("landing.languages.title")}
            </h2>
            <p className="mt-4 max-w-xl text-body-lg text-muted">{t("landing.languages.body")}</p>
            <ul className="mt-8 grid gap-4 sm:grid-cols-3">
              {[
                { lang: "ta", text: "மூன்று நாட்களாக தலைவலி" },
                { lang: "hi", text: "तीन दिन से सिरदर्द है" },
                { lang: "en", text: "Headache for three days" },
              ].map((sample) => (
                <li
                  key={sample.lang}
                  lang={sample.lang}
                  className="rounded-lg border border-paper-line bg-paper px-4 py-3 text-body-lg text-paper-ink"
                >
                  {sample.text}
                </li>
              ))}
            </ul>
          </div>
        </Section>

        {/* Doctor — the page's one deliberate dark block, matching the clinician app. */}
        <Section labelledBy="doctor-title" className="py-16 lg:py-24">
          <div data-reveal className="overflow-hidden rounded-2xl bg-ink px-6 py-10 text-white sm:px-10 lg:px-14 lg:py-16">
            <div className="grid gap-8 lg:grid-cols-2 lg:items-center lg:gap-14">
              <div>
                <h2 id="doctor-title" className="text-title text-balance text-white">
                  {t("landing.doctor.title")}
                </h2>
                <p className="mt-4 max-w-lg text-body-lg text-white/75">{t("landing.doctor.body")}</p>
              </div>
              <ul className="flex flex-col gap-3">
                {[
                  { icon: FileText, label: t("provenance.document"), body: t("case.documents") },
                  { icon: ShieldCheck, label: t("provenance.confirmed"), body: t("ai.confirmedByPatient") },
                  { icon: Stethoscope, label: t("provenance.doctor"), body: t("case.assessment") },
                ].map(({ icon: Icon, label, body }) => (
                  <li key={label} className="flex items-start gap-3 rounded-lg bg-white/[0.07] px-4 py-3">
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

        {/* Trust */}
        <Section labelledBy="trust-title" className="py-16 lg:py-24">
          <h2 id="trust-title" data-reveal className="max-w-2xl text-title text-ink">
            {t("landing.trust.title")}
          </h2>
          <ul className="mt-10 grid gap-4 md:grid-cols-3">
            {promises.map(({ key, Icon }) => (
              <li key={key} data-reveal className="rounded-xl border border-line bg-surface p-6">
                <Icon size={24} weight="regular" aria-hidden className="text-brand" />
                <p className="mt-3 text-body text-ink">{t(`landing.trust.${key}`)}</p>
              </li>
            ))}
          </ul>
        </Section>

        {/* Call to action */}
        <Section className="pb-20 pt-4 lg:pb-28">
          <div data-reveal className="rounded-2xl bg-brand px-6 py-12 text-center text-white sm:px-10 lg:py-16">
            <h2 className="mx-auto max-w-2xl text-title text-balance text-white">{t("landing.cta.title")}</h2>
            <p className="mx-auto mt-3 max-w-md text-body text-white/75">{t("landing.cta.body")}</p>
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
