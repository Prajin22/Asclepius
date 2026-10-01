"use client";

import { useT } from "@carebridge/i18n";
import type { CorpusLane, CorpusReviewState, IngestionState } from "@carebridge/shared-types";
import { Badge, cn, type Tone } from "@carebridge/ui";
import type { ReactNode } from "react";

const REVIEW_TONE: Record<CorpusReviewState, Tone> = {
  draft: "neutral",
  under_review: "info",
  approved: "success",
  rejected: "danger",
};

const INGESTION_TONE: Record<IngestionState, Tone> = {
  uploaded: "neutral",
  parsed: "success",
  needs_review: "warning",
  failed: "danger",
};

/** The lane is always shown in words, never by colour alone. */
export function LaneBadge({ lane }: { lane: CorpusLane }) {
  const t = useT();
  return <Badge tone={lane === "india" ? "brand" : "info"}>{t(`corpus.lane.${lane}`)}</Badge>;
}

export function ReviewBadge({ state }: { state: CorpusReviewState }) {
  const t = useT();
  return <Badge tone={REVIEW_TONE[state]}>{t(`corpus.reviewState.${state}`)}</Badge>;
}

export function IngestionBadge({ state }: { state: IngestionState }) {
  const t = useT();
  return <Badge tone={INGESTION_TONE[state]}>{t(`corpus.ingestion.${state}`)}</Badge>;
}

/** A SHA-256, in full: it is what an approval names, so it is never shortened. */
export function Checksum({ value, className }: { value: string; className?: string }) {
  return <code className={cn("break-all font-mono text-small text-ink", className)}>{value}</code>;
}

/** A definition list row for provenance panels. `stacked` puts the value under its label, for narrow columns. */
export function Fact({ label, children, stacked = false }: { label: ReactNode; children: ReactNode; stacked?: boolean }) {
  return (
    <div className={cn("grid gap-0.5 py-2.5", !stacked && "sm:grid-cols-[12rem_minmax(0,1fr)] sm:gap-4")}>
      <dt className="text-small font-semibold text-muted">{label}</dt>
      <dd className="min-w-0 text-ink">{children}</dd>
    </div>
  );
}

/** "Page 3" or "Pages 3–5". */
export function pageRange(t: (key: string, values?: Record<string, string | number>) => string, start: number, end: number): string {
  return start === end ? t("corpus.mark.selectionPage", { page: start }) : t("corpus.mark.selectionPages", { start, end });
}
