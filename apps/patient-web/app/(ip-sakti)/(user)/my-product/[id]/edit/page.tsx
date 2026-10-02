"use client";

import { useApi, useQuery } from "@carebridge/api-client/react";
import { useT } from "@carebridge/i18n";
import { ErrorState, PageHeader, SkeletonCard } from "@carebridge/ui";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeftIcon } from "@/components/icons";
import { ProductEditor } from "@/components/sakti/classify/ProductEditor";

/** Edit a product's description. A saved edit is a new version; earlier classifications keep the version they used. */
export default function EditProductPage() {
  const { id } = useParams<{ id: string }>();
  const api = useApi();
  const router = useRouter();
  const t = useT();
  const q = useQuery((a) => a.products.get(id), [id]);

  if (q.error && !q.data) return <ErrorState error={q.error} onRetry={q.reload} />;
  if (!q.data) return <SkeletonCard />;
  return (
    <>
      <PageHeader
        back={
          <Link href={`/my-product/${id}`} className="inline-flex items-center gap-1.5 font-medium text-brand-strong hover:underline">
            <ArrowLeftIcon aria-hidden />
            {q.data.name}
          </Link>
        }
        title={t("product.editTitle")}
        description={t("product.editDescription")}
      />
      <ProductEditor
        product={q.data}
        onCancel={() => router.push(`/my-product/${id}`)}
        onSubmit={async (values) => {
          await api.products.update(id, values);
          router.push(`/my-product/${id}`);
        }}
      />
    </>
  );
}
