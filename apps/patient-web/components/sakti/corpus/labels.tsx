"use client";

import { useT } from "@carebridge/i18n";
import type { CorpusLane, CorpusReviewState, IngestionState } from "@carebridge/shared-types";
import { Badge, cn, type Tone } from "@carebridge/ui";
import {
  CheckCircle,
  CircleDashed,
  HourglassMedium,
  PencilSimpleLine,
  SealCheck,
  Warning,
  WarningCircle,
  XCircle,
} from "@phosphor-icons/react/dist/ssr";
import type { Icon } from "@phosphor-icons/react";
import type { ReactNode } from "react";
import { LaneMark } from "../ui";

const REVIEW: Record<CorpusReviewState, { tone: Tone; icon: Icon }> = {
  draft: { tone: "neutral", icon: PencilSimpleLine },
  under_review: { tone: "info", icon: HourglassMedium },
  approved: { tone: "success", icon: SealCheck },
  rejected: { tone: "danger", icon: XCircle },
};

const INGESTION: Record<IngestionState, { tone: Tone; icon: Icon }> = {
  uploaded: { tone: "neutral", icon: CircleDashed },
  parsed: { tone: "success", icon: CheckCircle },
  needs_review: { tone: "warning", icon: Warning },
  failed: { tone: "danger", icon: WarningCircle },
};

/** The lane is always shown in words and with its own icon, never by colour alone. */
export function LaneBadge({ lane }: { lane: CorpusLane }) {
  return <LaneMark lane={lane} size="sm" />;
}

export function ReviewBadge({ state }: { state: CorpusReviewState }) {
  const t = useT();
  const { tone, icon: Glyph } = REVIEW[state];
  return (
    <Badge tone={tone}>
      <Glyph size={13} weight="bold" aria-hidden />
      {t(`corpus.reviewState.${state}`)}
    </Badge>
  );
}

export function IngestionBadge({ state }: { state: IngestionState }) {
  const t = useT();
  const { tone, icon: Glyph } = INGESTION[state];
  return (
    <Badge tone={tone}>
      <Glyph size={13} weight="bold" aria-hidden />
      {t(`corpus.ingestion.${state}`)}
    </Badge>
  );
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
