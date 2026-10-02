"use client";

import { useApi } from "@carebridge/api-client/react";
import { errorMessage, useI18n } from "@carebridge/i18n";
import { Alert, Button, ErrorState, PageHeader, SkeletonCard, buttonClasses, cn } from "@carebridge/ui";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { ProductIcon } from "@/components/icons";
import { EmptyPanel, StateBadge } from "../ui";
import { useProductOverview } from "./overview";
import { ClassificationTimeline } from "./status";

export { STATUS_TONE } from "./status";

/** Classify: choose one of your products, then start or continue its classification. */
export function ClassifyStart() {
  const api = useApi();
  const router = useRouter();
  const params = useSearchParams();
  const { t } = useI18n();
  const q = useProductOverview();
  const [chosen, setChosen] = useState<string | null>(params.get("product"));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const list = q.data ?? [];
  const item = list.find((p) => p.product.id === chosen) ?? list[0];

  async function start() {
    if (!item) return;
    setBusy(true);
    setError(null);
    try {
      const session = await api.classifier.start(item.product.id);
      router.push(`/classify/${session.id}`);
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title={t("pages.classify.title")} description={t("pages.classify.description")} />
      {q.error && !q.data ? (
        <ErrorState error={q.error} onRetry={q.reload} />
      ) : !q.data ? (
        <SkeletonCard />
      ) : list.length === 0 ? (
        <EmptyPanel
          icon={ProductIcon}
          title={t("product.emptyTitle")}
          action={
            <Link href="/my-product/new" className={buttonClasses("primary", "md")}>
              {t("product.add")}
            </Link>
          }
        >
          {t("classifier.start.noProducts")}
        </EmptyPanel>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="flex min-w-0 flex-col gap-5">
            <fieldset className="rounded-md border border-line bg-surface p-5 sm:p-6">
              <legend className="sr-only">{t("classifier.start.product")}</legend>
              <p className="text-subheading text-ink" aria-hidden>
                {t("classifier.start.product")}
              </p>
              <p className="mt-0.5 text-small text-muted">{t("classifier.start.productHint")}</p>
              <div className="mt-4 flex flex-col gap-2.5">
                {list.map(({ product, state }) => (
                  <label
                    key={product.id}
                    className={cn(
                      "flex cursor-pointer items-center gap-3 rounded-md border px-4 py-3 transition-colors duration-150",
                      item?.product.id === product.id ? "border-brand bg-brand-tint ring-1 ring-brand" : "border-line hover:bg-sunken",
                    )}
                  >
                    <input
                      type="radio"
                      name="product"
                      value={product.id}
                      checked={item?.product.id === product.id}
                      onChange={() => setChosen(product.id)}
                      className="size-5 shrink-0 accent-[var(--color-brand)]"
                    />
                    <span className="min-w-0 flex-1 font-medium text-ink">{product.name}</span>
                    <StateBadge state={state} className="shrink-0 max-sm:hidden" />
                  </label>
                ))}
              </div>
            </fieldset>

            {item ? (
              <div className="flex flex-col gap-4 rounded-md border border-line bg-surface p-5 sm:p-6">
                <div className="flex flex-wrap items-center gap-2">
                  <StateBadge state={item.state} />
                </div>
                <p className="text-muted">{t(`classifier.start.state.${item.state}`)}</p>
                {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
                <ol className="grid gap-2 text-small text-muted sm:grid-cols-3">
                  {(["one", "two", "three"] as const).map((k, i) => (
                    <li key={k} className="flex gap-2 rounded-md bg-sunken p-3">
                      <span aria-hidden className="font-bold text-brand-strong">
                        {i + 1}
                      </span>
                      {t(`classifier.start.how.${k}`)}
                    </li>
                  ))}
                </ol>
                <div className="flex flex-wrap gap-2">
                  {item.product.open_session_id ? (
                    <Link href={`/classify/${item.product.open_session_id}`} className={buttonClasses("primary", "md")}>
                      {t("classifier.start.continue")}
                    </Link>
                  ) : (
                    <Button onClick={start} disabled={busy}>
                      {busy ? t("classifier.session.restarting") : t("classifier.start.begin")}
                    </Button>
                  )}
                  <Link href={`/my-product/${item.product.id}`} className={buttonClasses("ghost", "md")}>
                    {t("classifier.start.viewProduct")}
                  </Link>
                </div>
              </div>
            ) : null}
          </div>

          {item ? (
            <section aria-labelledby="history-title" className="h-fit rounded-md border border-line bg-surface p-5">
              <h2 id="history-title" className="text-subheading text-ink">
                {t("classifier.start.history")}
              </h2>
              <p className="mb-4 mt-0.5 text-small text-muted">{item.product.name}</p>
              <ClassificationTimeline history={item.history} />
            </section>
          ) : null}
        </div>
      )}
    </>
  );
}
