"use client";

import { SkeletonCard } from "@carebridge/ui";
import { Suspense } from "react";
import { ClassifyStart } from "@/components/sakti/classify/ClassifyStart";

/** Phase 3: choose a product and classify it. */
export default function ClassifyPage() {
  // useSearchParams needs a boundary so the page can still be prerendered.
  return (
    <Suspense fallback={<SkeletonCard />}>
      <ClassifyStart />
    </Suspense>
  );
}
