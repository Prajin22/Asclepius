"use client";

import { useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import type { ReferenceStatus } from "@carebridge/shared-types";
import { ErrorState, Skeleton, SkeletonCard, buttonClasses, cn } from "@carebridge/ui";
import { ArrowRight, BookOpenText, CheckCircle, CircleDashed, Clock, Plus, WarningCircle } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { AskIcon, ClassifyIcon, ProductIcon } from "@/components/icons";
import { ProductCard } from "../classify/MyProducts";
import { useProductOverview } from "../classify/overview";
import { SampleProductButton } from "../classify/SampleProduct";
import { SessionBadge } from "../classify/status";
import { EmptyPanel, InfoOnly, ReadinessItem } from "../ui";

/**
 * The user's dashboard. Everything on it is read from the API as it stands:
 * the user's products, their latest classification, and whether the
 * classifier's legal references are backed by approved text yet. What does not
 * exist yet — the source-grounded answer service — is listed as not ready,
 * never shown as working.
 */
export function Dashboard() {
  const { t, formatDateTime } = useI18n();
  const router = useRouter();
  const overview = useProductOverview();
  const tree = useQuery((a) => a.classifier.tree());

  const items = overview.data ?? [];
  const latest = items
    .flatMap(({ product, history }) => history.map((s) => ({ product, session: s })))
    .sort((a, b) => b.session.created_at.localeCompare(a.session.created_at))[0];
  const slots = tree.data?.slots ?? [];
  const count = (s: ReferenceStatus) => slots.filter((x) => x.status === s).length;
  const hasProduct = items.length > 0;
  const hasConfirmed = items.some((i) => i.state === "confirmed");
  const allVerified = slots.length > 0 && count("verified") === slots.length;

  return (
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
      {/* Hero */}
      <section aria-labelledby="dash-title" className="rounded-md border border-line bg-surface p-6 sm:p-8 xl:col-span-2">
        <p className="text-label uppercase text-brand-strong">{t("app.domain")}</p>
        <h1 id="dash-title" className="mt-3 max-w-2xl text-title text-ink [overflow-wrap:anywhere]">
          {t("dashboard.hero.title")}
        </h1>
        <p className="mt-3 max-w-2xl text-body-lg text-muted">{t("dashboard.hero.lead")}</p>
        <div className="mt-6 flex flex-wrap gap-2.5">
          <Link href="/my-product/new" className={buttonClasses("primary", "md")}>
            <Plus size={18} weight="bold" aria-hidden />
            {t("dashboard.actions.add")}
          </Link>
          <Link href="/classify" className={buttonClasses("secondary", "md")}>
            <ClassifyIcon size={18} aria-hidden />
            {t("dashboard.actions.classify")}
          </Link>
          <Link href="/ask" className={buttonClasses("secondary", "md")}>
            <AskIcon size={18} aria-hidden />
            {t("dashboard.actions.ask")}
          </Link>
        </div>
      </section>

      {/* Readiness */}
      <section aria-labelledby="dash-ready" className="rounded-md border border-line bg-surface p-5 sm:p-6">
        <h2 id="dash-ready" className="text-subheading text-ink">
          {t("dashboard.readiness.title")}
        </h2>
        <p className="mt-0.5 text-small text-muted">{t("dashboard.readiness.hint")}</p>
        {overview.data && tree.data ? (
          <ul className="mt-2 divide-y divide-line">
            <ReadinessItem
              done={hasProduct}
              label={t("dashboard.readiness.product")}
              note={t(hasProduct ? "dashboard.readiness.productDone" : "dashboard.readiness.productTodo")}
            />
            <ReadinessItem
              done={hasConfirmed}
              label={t("dashboard.readiness.classification")}
              note={t(hasConfirmed ? "dashboard.readiness.classificationDone" : "dashboard.readiness.classificationTodo")}
            />
            <ReadinessItem
              done={allVerified}
              label={t("dashboard.readiness.corpus")}
              note={t("dashboard.readiness.corpusNote", { verified: count("verified"), total: slots.length })}
            />
            <ReadinessItem done={false} label={t("dashboard.readiness.answers")} note={t("dashboard.readiness.answersNote")} />
          </ul>
        ) : overview.error || tree.error ? (
          <ErrorState error={overview.error ?? tree.error} onRetry={() => (overview.error ? overview.reload() : tree.reload())} />
        ) : (
          <div className="mt-4 flex flex-col gap-3">
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
          </div>
        )}
      </section>

      {/* My products */}
      <section aria-labelledby="dash-products" className="flex flex-col gap-3 xl:col-span-2">
        <SectionHead id="dash-products" title={t("dashboard.products.title")} href="/my-product" link={t("dashboard.products.all")} />
        {overview.error && !overview.data ? (
          <ErrorState error={overview.error} onRetry={overview.reload} />
        ) : !overview.data ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <SkeletonCard />
            <SkeletonCard />
          </div>
        ) : items.length === 0 ? (
          <EmptyPanel
            icon={ProductIcon}
            title={t("product.emptyTitle")}
            action={
              <span className="flex flex-wrap items-start justify-center gap-2">
                <Link href="/my-product/new" className={buttonClasses("primary", "md")}>
                  {t("product.add")}
                </Link>
                <SampleProductButton onCreated={(p) => router.push(`/my-product/${p.id}`)} />
              </span>
            }
          >
            {t("product.empty")}
          </EmptyPanel>
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2">
            {items.slice(0, 4).map((item) => (
              <li key={item.product.id} className="flex">
                <ProductCard item={item} />
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Getting started */}
      <section aria-labelledby="dash-start" className="h-fit rounded-md border border-line bg-surface p-5 sm:p-6">
        <h2 id="dash-start" className="text-subheading text-ink">
          {t("dashboard.start.title")}
        </h2>
        <ol className="mt-4 flex flex-col gap-4">
          <Step n={1} title={t("dashboard.start.one")} body={t("dashboard.start.oneBody")} href="/my-product/new" link={t("dashboard.actions.add")} />
          <Step n={2} title={t("dashboard.start.two")} body={t("dashboard.start.twoBody")} href="/classify" link={t("dashboard.actions.classify")} />
          <Step n={3} title={t("dashboard.start.three")} body={t("dashboard.start.threeBody")} />
          <Step n={4} title={t("dashboard.start.four")} body={t("dashboard.start.fourBody")} later />
        </ol>
      </section>

      {/* Recent classification */}
      <section aria-labelledby="dash-recent" className="flex flex-col rounded-md border border-line bg-surface p-5 sm:p-6 xl:col-span-2">
        <h2 id="dash-recent" className="text-subheading text-ink">
          {t("dashboard.recent.title")}
        </h2>
        {!overview.data ? (
          <Skeleton className="mt-4 h-20" />
        ) : !latest ? (
          <p className="mt-3 text-muted">{t("dashboard.recent.empty")}</p>
        ) : (
          <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <SessionBadge status={latest.session.status} />
              <p className="mt-2 text-heading text-ink">
                {latest.session.category
                  ? t(`classifier.category.${latest.session.category}`)
                  : t("classifier.timeline.noCategory")}
              </p>
              <p className="mt-1 text-small text-muted">
                {t("dashboard.recent.meta", {
                  product: latest.product.name,
                  date: formatDateTime(latest.session.created_at),
                  version: latest.session.tree_version,
                })}
              </p>
            </div>
            <Link href={`/classify/${latest.session.id}`} className={buttonClasses("secondary", "md", "shrink-0")}>
              {t("dashboard.recent.open")}
              <ArrowRight size={16} aria-hidden />
            </Link>
          </div>
        )}
        {/* The note sits at the foot of the card, however tall its neighbour makes it. */}
        <div className="mt-auto pt-5">
          <InfoOnly className="border-t border-line pt-4" />
        </div>
      </section>

      {/* Reference status */}
      <section aria-labelledby="dash-refs" className="rounded-md border border-line bg-surface p-5 sm:p-6">
        <h2 id="dash-refs" className="flex items-center gap-2 text-subheading text-ink">
          <BookOpenText size={20} aria-hidden className="text-brand" />
          {t("dashboard.references.title")}
        </h2>
        <p className="mt-0.5 text-small text-muted">{t("dashboard.references.hint")}</p>
        {tree.data ? (
          <ul className="mt-4 flex flex-col gap-2">
            <RefCount icon={<CheckCircle size={18} weight="fill" className="text-success" aria-hidden />} label={t("classifier.reference.verified")} n={count("verified")} />
            <RefCount icon={<WarningCircle size={18} weight="bold" className="text-warning" aria-hidden />} label={t("classifier.reference.unverified")} n={count("unverified")} />
            <RefCount icon={<CircleDashed size={18} weight="bold" className="text-subtle" aria-hidden />} label={t("classifier.reference.corpus_required")} n={count("corpus_required")} />
          </ul>
        ) : tree.error ? (
          <ErrorState error={tree.error} onRetry={tree.reload} />
        ) : (
          <Skeleton className="mt-4 h-24" />
        )}
        <p className="mt-4 border-t border-line pt-3 text-caption text-subtle">{t("classifier.reference.corpusRequiredNote")}</p>
      </section>
    </div>
  );
}

function SectionHead({ id, title, href, link }: { id: string; title: string; href: string; link: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <h2 id={id} className="text-heading text-ink">
        {title}
      </h2>
      <Link href={href} className="inline-flex min-h-11 items-center gap-1 text-small font-semibold text-brand-strong hover:underline sm:min-h-0">
        {link}
        <ArrowRight size={14} aria-hidden />
      </Link>
    </div>
  );
}

function Step({ n, title, body, href, link, later }: { n: number; title: string; body: string; href?: string; link?: string; later?: boolean }) {
  const { t } = useI18n();
  return (
    <li className="flex gap-3">
      <span
        aria-hidden
        className={cn(
          "grid size-7 shrink-0 place-items-center rounded-full text-small font-bold",
          later ? "border border-dashed border-line-strong text-subtle" : "bg-brand-soft text-brand-strong",
        )}
      >
        {n}
      </span>
      <div className="min-w-0">
        <p className={cn("font-semibold", later ? "text-muted" : "text-ink")}>{title}</p>
        <p className="text-small text-muted">{body}</p>
        {later ? (
          <p className="mt-1 inline-flex items-center gap-1 text-caption font-medium text-subtle">
            <Clock size={13} aria-hidden />
            {t("ui.laterRelease")}
          </p>
        ) : null}
        {href && link ? (
          <Link href={href} className="mt-1 inline-flex min-h-11 items-center gap-1 text-small font-semibold text-brand-strong hover:underline sm:min-h-0">
            {link}
            <ArrowRight size={14} aria-hidden />
          </Link>
        ) : null}
      </div>
    </li>
  );
}

function RefCount({ icon, label, n }: { icon: ReactNode; label: string; n: number }) {
  return (
    <li className="flex items-center justify-between gap-3 rounded-md bg-sunken px-3 py-2">
      <span className="flex min-w-0 items-center gap-2 text-small font-medium text-ink">
        <span className="shrink-0">{icon}</span>
        <span className="min-w-0 [overflow-wrap:anywhere]">{label}</span>
      </span>
      <span className="shrink-0 text-value text-ink">{n}</span>
    </li>
  );
}
