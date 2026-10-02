"use client";

import { useApi } from "@carebridge/api-client/react";
import { useT } from "@carebridge/i18n";
import { PageHeader } from "@carebridge/ui";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeftIcon } from "@/components/icons";
import { ProductEditor } from "@/components/sakti/classify/ProductEditor";

/** Describe a new product. Saving opens it, or goes straight on to classify it. */
export default function NewProductPage() {
  const api = useApi();
  const router = useRouter();
  const t = useT();
  return (
    <>
      <PageHeader
        back={
          <Link href="/my-product" className="inline-flex items-center gap-1.5 font-medium text-brand-strong hover:underline">
            <ArrowLeftIcon aria-hidden />
            {t("pages.myProduct.title")}
          </Link>
        }
        title={t("product.new.title")}
        description={t("product.new.description")}
      />
      <ProductEditor
        onCancel={() => router.push("/my-product")}
        onSubmit={async (values, then) => {
          const created = await api.products.create(values);
          if (then === "classify") {
            const session = await api.classifier.start(created.id);
            router.push(`/classify/${session.id}`);
          } else router.push(`/my-product/${created.id}`);
        }}
      />
    </>
  );
}
