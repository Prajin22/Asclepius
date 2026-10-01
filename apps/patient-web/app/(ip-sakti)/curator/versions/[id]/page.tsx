"use client";

import { useParams } from "next/navigation";
import { VersionReview } from "@/components/sakti/corpus/VersionReview";

export default function VersionPage() {
  const { id } = useParams<{ id: string }>();
  return <VersionReview id={id} />;
}
