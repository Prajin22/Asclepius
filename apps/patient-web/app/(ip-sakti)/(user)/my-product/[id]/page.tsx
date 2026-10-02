"use client";

import { useParams } from "next/navigation";
import { ProductDetail } from "@/components/sakti/classify/ProductDetail";

/** One product, its description and its classification history. */
export default function ProductPage() {
  const { id } = useParams<{ id: string }>();
  return <ProductDetail id={id} />;
}
