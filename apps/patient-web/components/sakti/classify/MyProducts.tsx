"use client";

import { useApi, useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import type { ProductProfile } from "@carebridge/shared-types";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, SkeletonCard, buttonClasses } from "@carebridge/ui";
import Link from "next/link";
import { useState } from "react";
import { ProductForm } from "./ProductForm";

/** My Product: the user's own products, described in their own words. */
export function MyProducts() {
  const api = useApi();
  const { t } = useI18n();
  const q = useQuery((a) => a.products.list());
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);

  const replace = (updated: ProductProfile) =>
    q.setData((q.data ?? []).map((p) => (p.id === updated.id ? updated : p)));

  return (
    <>
      <PageHeader
        title={t("pages.myProduct.title")}
        description={t("pages.myProduct.description")}
        actions={
          adding ? null : (
            <Button onClick={() => setAdding(true)} disabled={editing !== null}>
              {t("product.add")}
            </Button>
          )
        }
      />
      <div className="flex max-w-3xl flex-col gap-5">
        {adding ? (
          <Card aria-label={t("product.add")}>
            <ProductForm
              onCancel={() => setAdding(false)}
              onSubmit={async (values) => {
                const created = await api.products.create(values);
                q.setData([created, ...(q.data ?? [])]);
                setAdding(false);
              }}
            />
          </Card>
        ) : null}

        {q.error && !q.data ? (
          <ErrorState error={q.error} onRetry={q.reload} />
        ) : !q.data ? (
          <SkeletonCard />
        ) : q.data.length === 0 && !adding ? (
          <EmptyState>{t("product.empty")}</EmptyState>
        ) : (
          <ul className="flex flex-col gap-4">
            {q.data.map((product) => (
              <li key={product.id}>
                <Card aria-labelledby={`product-${product.id}`}>
                  {editing === product.id ? (
                    <ProductForm
                      product={product}
                      onCancel={() => setEditing(null)}
                      onSubmit={async (values) => {
                        replace(await api.products.update(product.id, values));
                        setEditing(null);
                      }}
                    />
                  ) : (
                    <ProductSummary product={product} onEdit={() => setEditing(product.id)} disabled={adding} />
                  )}
                </Card>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}

function ProductSummary({ product, onEdit, disabled }: { product: ProductProfile; onEdit: () => void; disabled: boolean }) {
  const { t } = useI18n();
  const confirmed = product.confirmed_classification;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 id={`product-${product.id}`} className="text-subheading text-ink">
            {product.name}
          </h2>
          <p className="text-small text-muted">{t("product.revision", { number: product.revision })}</p>
        </div>
        {confirmed ? (
          <Badge tone="success">{t("product.confirmedAs", { category: t(`classifier.category.${confirmed.category}`) })}</Badge>
        ) : product.open_session_id ? (
          <Badge tone="info">{t("product.inProgress")}</Badge>
        ) : (
          <Badge tone="neutral">{t("product.notClassified")}</Badge>
        )}
      </div>
      {product.intended_use ? <p className="text-ink">{product.intended_use}</p> : null}
      {product.ingredients.length ? (
        <p className="text-small text-muted">
          {t("product.field.ingredients")}: {product.ingredients.map((i) => i.name).join(", ")}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Link href={`/classify?product=${product.id}`} className={buttonClasses("primary", "sm")}>
          {t("product.classify")}
        </Link>
        <Button variant="secondary" size="sm" onClick={onEdit} disabled={disabled}>
          {t("product.edit")}
        </Button>
      </div>
    </div>
  );
}
