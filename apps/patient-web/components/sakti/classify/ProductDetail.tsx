"use client";

import { useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import { languageInfo, type ProductProfile } from "@carebridge/shared-types";
import { ErrorState, PageHeader, SkeletonCard, buttonClasses } from "@carebridge/ui";
import { PencilSimple } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowLeftIcon } from "@/components/icons";
import { DemoTag, InfoOnly, StateBadge } from "../ui";
import { nextStep } from "./MyProducts";
import { isDemoProduct, productState } from "./overview";
import { ClassificationTimeline } from "./status";

/** One product: where its classification stands, the user's own description, and every classification so far. */
export function ProductDetail({ id }: { id: string }) {
  const { t, formatDate, formatDateTime } = useI18n();
  const q = useQuery(async (api) => {
    const [product, history] = await Promise.all([api.products.get(id), api.products.classifications(id)]);
    return { product, history };
  }, [id]);

  if (q.error && !q.data) return <ErrorState error={q.error} onRetry={q.reload} />;
  if (!q.data) return <SkeletonCard />;
  const { product, history } = q.data;
  const state = productState(product, history);
  const next = nextStep({ product, state });
  const confirmed = product.confirmed_classification;

  return (
    <>
      <PageHeader
        back={
          <Link href="/my-product" className="inline-flex items-center gap-1.5 font-medium text-brand-strong hover:underline">
            <ArrowLeftIcon aria-hidden />
            {t("pages.myProduct.title")}
          </Link>
        }
        title={product.name}
        description={t("product.card.updated", { date: formatDate(product.updated_at), number: product.revision })}
        actions={
          <Link href={`/my-product/${product.id}/edit`} className={buttonClasses("secondary", "md")}>
            <PencilSimple size={18} aria-hidden />
            {t("product.edit")}
          </Link>
        }
      />

      <div className="flex flex-col gap-6">
        <section
          aria-labelledby="product-state"
          className="flex flex-col gap-4 rounded-md border border-line bg-surface p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6"
        >
          <div className="min-w-0">
            <h2 id="product-state" className="sr-only">
              {t("product.detail.stateTitle")}
            </h2>
            <div className="flex flex-wrap items-center gap-2">
              <StateBadge state={state} />
              {isDemoProduct(product) ? <DemoTag /> : null}
            </div>
            {confirmed ? (
              <p className="mt-2 text-heading text-ink">{t(`classifier.category.${confirmed.category}`)}</p>
            ) : null}
            <p className="mt-1.5 max-w-2xl text-muted">
              {confirmed && state === "confirmed"
                ? t("product.detail.state.confirmed", { date: formatDateTime(confirmed.decided_at) })
                : t(`product.detail.state.${state}`)}
            </p>
          </div>
          <Link
            href={state === "confirmed" ? `/classify?product=${product.id}` : next.href}
            className={buttonClasses("primary", "md", "shrink-0")}
          >
            {t(state === "confirmed" ? "product.action.again" : next.label)}
          </Link>
        </section>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <ProductFacts product={product} />
          <section aria-labelledby="history" className="h-fit rounded-md border border-line bg-surface p-5 sm:p-6">
            <h2 id="history" className="text-subheading text-ink">
              {t("classifier.timeline.title")}
            </h2>
            <p className="mb-5 mt-0.5 text-small text-muted">{t("classifier.timeline.hint")}</p>
            <ClassificationTimeline history={history} />
          </section>
        </div>
        <InfoOnly />
      </div>
    </>
  );
}

/** The user's own description, section by section, exactly as written. Blank parts say so. */
function ProductFacts({ product }: { product: ProductProfile }) {
  const { t } = useI18n();
  const none = <span className="text-subtle">{t("product.none")}</span>;
  const text = (v: string | null) => (v ? <span className="whitespace-pre-line">{v}</span> : none);
  const rows: [string, ReactNode][] = [
    ["product.section.identity.title", <Pairs key="i" items={[
      [t("product.field.name"), product.name],
      [t("product.field.text_language"), product.text_language ? languageInfo(product.text_language)?.nativeName ?? none : none],
    ]} />],
    ["product.section.purpose.title", text(product.intended_use)],
    ["product.section.form.title", <Pairs key="f" items={[
      [t("product.field.dosage_form"), text(product.dosage_form)],
      [t("product.field.administration_route"), product.administration_route ? t(`product.route.${product.administration_route}`) : none],
    ]} />],
    [
      "product.section.ingredients.title",
      product.ingredients.length ? (
        <ul className="flex flex-col divide-y divide-line rounded-md border border-line">
          {product.ingredients.map((i, n) => (
            <li key={n} className="grid gap-1 px-3.5 py-2.5 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)]">
              <span className="font-medium text-ink">{i.name}</span>
              <span className="text-small text-muted">
                <span className="sr-only">{t("product.ingredient.part_used")}: </span>
                {i.part_used ?? "—"}
              </span>
              <span className="text-small text-muted">
                <span className="sr-only">{t("product.ingredient.quantity")}: </span>
                {i.quantity ?? "—"}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        none
      ),
    ],
    ["product.section.preparation.title", text(product.preparation_method)],
    ["product.section.classical.title", text(product.classical_reference)],
    ["product.section.extract.title", <Pairs key="e" items={[
      [t("product.field.extract_description"), text(product.extract_description)],
      [t("product.field.standardization_description"), text(product.standardization_description)],
    ]} />],
    [
      "product.section.markers.title",
      product.markers.length ? (
        <ul className="flex flex-wrap gap-1.5">
          {product.markers.map((m, n) => (
            <li key={n} className="rounded-sm border border-line bg-sunken px-2 py-0.5 text-small text-ink">
              {m}
            </li>
          ))}
        </ul>
      ) : (
        none
      ),
    ],
    ["product.section.notes.title", text(product.notes)],
  ];
  return (
    <section aria-labelledby="facts" className="rounded-md border border-line bg-surface">
      <div className="border-b border-line px-5 py-4 sm:px-6">
        <h2 id="facts" className="text-subheading text-ink">
          {t("product.detail.factsTitle")}
        </h2>
        <p className="mt-0.5 text-small text-muted">{t("product.factsNote")}</p>
      </div>
      <dl className="divide-y divide-line">
        {rows.map(([key, value], i) => (
          <div key={key} className="grid gap-1.5 px-5 py-4 sm:grid-cols-[12rem_minmax(0,1fr)] sm:gap-4 sm:px-6">
            <dt className="text-small font-semibold text-muted">
              <span aria-hidden className="mr-1.5 text-subtle">
                {i + 1}.
              </span>
              {t(key)}
            </dt>
            <dd className="min-w-0 text-ink">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Pairs({ items }: { items: [string, ReactNode][] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {items.map(([label, value]) => (
        <div key={label} className="min-w-0">
          <p className="text-caption text-subtle">{label}</p>
          <div className="text-ink">{value}</div>
        </div>
      ))}
    </div>
  );
}
