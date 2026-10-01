"use client";

import { useParams } from "next/navigation";
import { SourceReview } from "@/components/sakti/corpus/SourceReview";

export default function SourcePage() {
  const { id } = useParams<{ id: string }>();
  return <SourceReview id={id} />;
}
