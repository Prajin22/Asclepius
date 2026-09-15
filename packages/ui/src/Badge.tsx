"use client";

import { useT } from "@carebridge/i18n";
import { languageInfo, type ConsultationStatus, type LanguageCode, type RecordSource } from "@carebridge/shared-types";
import { CalendarCheck, CheckCircle, Clock, Prohibit, Pulse } from "@phosphor-icons/react/dist/ssr";
import type { ReactNode } from "react";
import { cn } from "./cn";
import { ProvenanceChip, type ProvenanceKind } from "./Provenance";

export type Tone = "neutral" | "brand" | "info" | "success" | "warning" | "danger" | "ai" | "mark";

const tones: Record<Tone, string> = {
  neutral: "border-line bg-sunken text-muted",
  brand: "border-brand/30 bg-brand-soft text-brand-strong",
  info: "border-info/25 bg-info-soft text-info",
  success: "border-success/25 bg-success-soft text-success",
  warning: "border-warning/25 bg-warning-soft text-warning",
  danger: "border-danger/30 bg-danger-soft text-danger",
  ai: "border-dashed border-ai-line bg-ai-soft text-ai",
  mark: "border-mark-ink/40 bg-mark-soft text-mark-ink",
};

/** A paper tag: square corners, one line, wraps rather than overflowing its column. */
export function Badge({ tone = "neutral", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 rounded-sm border px-2 py-0.5 text-caption font-semibold",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/**
 * Where a consultation stands. The four folds of a consultation are requested,
 * accepted, active and completed; each carries an icon and a word as well as a tone.
 */
const statusTone: Record<ConsultationStatus, Tone> = {
  requested: "mark",
  accepted: "info",
  active: "success",
  completed: "neutral",
  cancelled: "danger",
};

const statusIcon: Record<ConsultationStatus, typeof Clock> = {
  requested: Clock,
  accepted: CalendarCheck,
  active: Pulse,
  completed: CheckCircle,
  cancelled: Prohibit,
};

export function StatusBadge({ status }: { status: ConsultationStatus }) {
  const t = useT();
  const Glyph = statusIcon[status];
  return (
    <Badge tone={statusTone[status]}>
      <Glyph size={13} weight="bold" aria-hidden />
      {t(`status.${status}`)}
    </Badge>
  );
}

/** Where a record came from, in the shared fold language. */
const sourceKind: Record<RecordSource, ProvenanceKind> = {
  patient: "original",
  ai_extracted: "machine",
  doctor: "doctor",
};

export function SourceBadge({ source }: { source: RecordSource }) {
  const t = useT();
  return <ProvenanceChip kind={sourceKind[source]} label={t(`source.${source}`)} />;
}

/** Language autonym, tagged with `lang` so screen readers pronounce it correctly. */
export function LanguageTag({ code, className }: { code: LanguageCode | null | undefined; className?: string }) {
  const info = languageInfo(code);
  if (!info) return null;
  return (
    <span lang={info.code} className={cn("text-caption font-medium text-muted", className)}>
      {info.nativeName}
    </span>
  );
}
