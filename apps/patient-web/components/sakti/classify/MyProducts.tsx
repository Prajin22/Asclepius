"use client";

import { useI18n } from "@carebridge/i18n";
import { ErrorState, Field, PageHeader, Select, SkeletonCard, TextInput, buttonClasses } from "@carebridge/ui";
import { MagnifyingGlass, Plus } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ProductIcon } from "@/components/icons";
import { DemoTag, EmptyPanel, StateBadge, type ProductState } from "../ui";
import { isDemoProduct, useProductOverview, type ProductOverview } from "./overview";
import { SampleProductButton } from "./SampleProduct";

const STATES: ProductState[] = ["not_classified", "in_progress", "requires_information", "awaiting_confirmation", "confirmed"];

/** My Products: the user's own products as cards, searchable and filterable by where each one's classification stands. */
export function MyProducts() {
  const { t } = useI18n();
  const router = useRouter();
  const q = useProductOverview();
  const [query, setQuery] = useState("");
  const [state, setState] = useState<ProductState | "all">("all");

  const all = q.data ?? [];
  const needle = query.trim().toLocaleLowerCase();
  const shown = all.filter(
    ({ product, state: s }) =>
      (state === "all" || s === state) &&
      (!needle ||
        product.name.toLocaleLowerCase().includes(needle) ||
        product.ingredients.some((i) => i.name.toLocaleLowerCase().includes(needle))),
  );

  return (
    <>
      <PageHeader
        title={t("pages.myProduct.title")}
        description={t("pages.myProduct.description")}
        actions={
          <Link href="/my-product/new" className={buttonClasses("primary", "md")}>
            <Plus size={18} weight="bold" aria-hidden />
            {t("product.add")}
          </Link>
        }
      />

      {q.error && !q.data ? (
        <ErrorState error={q.error} onRetry={q.reload} />
      ) : !q.data ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : all.length === 0 ? (
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
        <div className="flex flex-col gap-5">
          <div className="grid gap-3 rounded-md border border-line bg-surface p-4 sm:grid-cols-[minmax(0,1fr)_16rem] sm:items-end">
            <Field label={t("product.search")}>
              {(p) => (
                <div className="relative">
                  <MagnifyingGlass size={18} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-subtle" />
                  <TextInput
                    {...p}
                    type="search"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder={t("product.searchPlaceholder")}
                    className="pl-10"
                  />
                </div>
              )}
            </Field>
            <Field label={t("product.filter")}>
              {(p) => (
                <Select {...p} value={state} onChange={(e) => setState(e.target.value as ProductState | "all")}>
                  <option value="all">{t("product.filterAll")}</option>
                  {STATES.map((s) => (
                    <option key={s} value={s}>
                      {t(`ui.state.${s}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>

          <p role="status" className="text-small text-muted">
            {t("product.showing", { shown: shown.length, total: all.length })}
          </p>

          {shown.length === 0 ? (
            <EmptyPanel
              icon={MagnifyingGlass}
              title={t("product.noMatch")}
              action={
                <button
                  type="button"
                  className={buttonClasses("secondary", "sm")}
                  onClick={() => {
                    setQuery("");
                    setState("all");
                  }}
                >
                  {t("product.clearFilters")}
                </button>
              }
            />
          ) : (
            <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {shown.map((item) => (
                <li key={item.product.id} className="flex">
                  <ProductCard item={item} />
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </>
  );
}

/** Where to go next from a product, by where its classification stands. */
export function nextStep({ product, state }: Pick<ProductOverview, "product" | "state">): { href: string; label: string } {
  switch (state) {
    case "not_classified":
      return { href: `/classify?product=${product.id}`, label: "product.action.classify" };
    case "in_progress":
    case "requires_information":
      return { href: `/classify/${product.open_session_id}`, label: "product.action.continue" };
    case "awaiting_confirmation":
      return { href: `/classify/${product.open_session_id}`, label: "product.action.review" };
    case "confirmed":
      return { href: `/my-product/${product.id}`, label: "product.action.view" };
  }
}

export function ProductCard({ item }: { item: ProductOverview }) {
  const { t, formatDate } = useI18n();
  const { product, state } = item;
  const next = nextStep(item);
  const confirmed = product.confirmed_classification;
  const headingId = `product-${product.id}`;
  return (
    <article
      aria-labelledby={headingId}
      className="flex w-full flex-col rounded-md border border-line bg-surface p-5 transition-shadow duration-150 hover:shadow-sm"
    >
      <div className="flex flex-wrap items-center gap-2">
        <StateBadge state={state} />
        {isDemoProduct(product) ? <DemoTag /> : null}
      </div>
      <h3 id={headingId} className="mt-3 text-subheading text-ink">
        <Link href={`/my-product/${product.id}`} className="rounded-sm hover:text-brand-strong hover:underline">
          {product.name}
        </Link>
      </h3>
      <p className="mt-1 line-clamp-2 text-small text-muted">{product.intended_use ?? t("product.card.noPurpose")}</p>
      <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-line pt-3 text-small">
        <div className="min-w-0">
          <dt className="text-caption text-subtle">{t("product.card.form")}</dt>
          <dd className="truncate text-ink">{product.dosage_form ?? t("product.none")}</dd>
        </div>
        <div>
          <dt className="text-caption text-subtle">{t("product.card.ingredients")}</dt>
          <dd className="text-ink">{product.ingredients.length}</dd>
        </div>
        {confirmed ? (
          <div className="col-span-2">
            <dt className="text-caption text-subtle">{t("product.card.confirmed")}</dt>
            <dd className="font-medium text-ink">{t(`classifier.category.${confirmed.category}`)}</dd>
          </div>
        ) : null}
      </dl>
      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-4">
        <span className="text-caption text-subtle">
          {t("product.card.updated", { date: formatDate(product.updated_at), number: product.revision })}
        </span>
        <Link href={next.href} className={buttonClasses(state === "confirmed" ? "secondary" : "primary", "sm")}>
          {t(next.label)}
          <span className="sr-only"> — {product.name}</span>
        </Link>
      </div>
    </article>
  );
}
