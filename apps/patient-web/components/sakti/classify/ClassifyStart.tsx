"use client";

import { useApi, useQuery } from "@carebridge/api-client/react";
import { errorMessage, useI18n } from "@carebridge/i18n";
import type { ClassificationStatus } from "@carebridge/shared-types";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  PageHeader,
  Select,
  SkeletonCard,
  buttonClasses,
  type Tone,
} from "@carebridge/ui";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

export const STATUS_TONE: Record<ClassificationStatus, Tone> = {
  incomplete: "info",
  requires_information: "warning",
  determined: "brand",
  user_confirmed: "success",
  user_rejected: "neutral",
  superseded: "neutral",
};

/** Classify: choose one of your products, then start or continue its classification. */
export function ClassifyStart() {
  const api = useApi();
  const router = useRouter();
  const params = useSearchParams();
  const { t, formatDateTime } = useI18n();
  const products = useQuery((a) => a.products.list());
  const [chosen, setChosen] = useState<string | null>(params.get("product"));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const list = products.data ?? [];
  const product = list.find((p) => p.id === chosen) ?? list[0];
  const history = useQuery(
    (a) => (product ? a.products.classifications(product.id) : Promise.resolve([])),
    [product?.id],
  );

  async function start() {
    if (!product) return;
    setBusy(true);
    setError(null);
    try {
      const session = await api.classifier.start(product.id);
      router.push(`/classify/${session.id}`);
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title={t("pages.classify.title")} description={t("pages.classify.description")} />
      <div className="flex max-w-3xl flex-col gap-5">
        {products.error && !products.data ? (
          <ErrorState error={products.error} onRetry={products.reload} />
        ) : !products.data ? (
          <SkeletonCard />
        ) : list.length === 0 ? (
          <EmptyState>
            <span className="flex flex-col items-center gap-3">
              {t("classifier.start.noProducts")}
              <Link href="/my-product" className={buttonClasses("primary", "sm")}>
                {t("classifier.start.toMyProduct")}
              </Link>
            </span>
          </EmptyState>
        ) : (
          <Card>
            <div className="flex flex-col gap-4">
              <Field label={t("classifier.start.product")}>
                {(p) => (
                  <Select {...p} value={product?.id ?? ""} onChange={(e) => setChosen(e.target.value)}>
                    {list.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
              <div>
                {product?.open_session_id ? (
                  <Link href={`/classify/${product.open_session_id}`} className={buttonClasses("primary", "md")}>
                    {t("classifier.start.continue")}
                  </Link>
                ) : (
                  <Button onClick={start} disabled={busy}>
                    {t("classifier.start.begin")}
                  </Button>
                )}
              </div>
            </div>
          </Card>
        )}

        {product ? (
          <section aria-labelledby="history-title" className="flex flex-col gap-3">
            <h2 id="history-title" className="text-subheading text-ink">
              {t("classifier.start.history")}
            </h2>
            {!history.data ? (
              <SkeletonCard />
            ) : history.data.length === 0 ? (
              <p className="text-muted">{t("classifier.start.noHistory")}</p>
            ) : (
              <Card padding="none" className="px-5 sm:px-6">
                <ul className="divide-y divide-line">
                  {history.data.map((session) => (
                    <li key={session.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                      <Link href={`/classify/${session.id}`} className="font-medium text-brand-strong hover:underline">
                        {session.category
                          ? t(`classifier.category.${session.category}`)
                          : t(`classifier.status.${session.status}`)}
                      </Link>
                      <span className="flex flex-wrap items-center gap-2 text-small text-muted">
                        <Badge tone={STATUS_TONE[session.status]}>{t(`classifier.status.${session.status}`)}</Badge>
                        {formatDateTime(session.created_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </section>
        ) : null}
      </div>
    </>
  );
}
