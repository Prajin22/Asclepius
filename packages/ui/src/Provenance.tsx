"use client";

import { useT } from "@carebridge/i18n";
import {
  ArrowsClockwise,
  CheckCircle,
  Clock,
  FileText,
  PaperPlaneTilt,
  Prohibit,
  Quotes,
  Scan,
  Stethoscope,
  Warning,
  WarningCircle,
} from "@phosphor-icons/react/dist/ssr";
import type { ReactNode } from "react";
import { cn } from "./cn";

/** Every Phosphor glyph shares one component type; derive it rather than import it. */
type Glyph = typeof CheckCircle;

/**
 * The fold language: where a piece of information came from, and what has been
 * done to it.
 *
 *   original / document  the sheet — vermilion washi, the patient's own material
 *   machine              a crease drawn but not pressed — dashed, quiet
 *   confirmed            the crease pressed — solid ink, only a person presses it
 *   doctor               sumi ink — authored, attributed, never machine-made
 *   needsReview          the gold mark — this is waiting for you
 *
 * Three things carry the source at once, never colour alone: the edge (solid,
 * dashed or inked), an icon, and a word.
 */
export type ProvenanceKind =
  | "original"
  | "document"
  | "machine"
  | "confirmed"
  | "doctor"
  | "needsReview"
  | "pending"
  | "rejected"
  | "processing"
  | "shared"
  | "failed";

const KINDS: Record<ProvenanceKind, { icon: Glyph; chip: string; block: string; labelKey: string }> = {
  original: {
    icon: Quotes,
    chip: "border-paper-line bg-paper text-paper-ink",
    block: "border-paper-line bg-paper",
    labelKey: "provenance.original",
  },
  document: {
    icon: FileText,
    chip: "border-paper-line bg-paper text-paper-ink",
    block: "border-paper-line bg-paper",
    labelKey: "provenance.document",
  },
  machine: {
    icon: Scan,
    chip: "border-dashed border-ai-line bg-ai-soft text-ai",
    block: "border-dashed border-ai-line bg-ai-soft",
    labelKey: "provenance.machine",
  },
  confirmed: {
    icon: CheckCircle,
    chip: "border-ink/40 bg-surface text-ink",
    block: "border-ink/60 bg-surface",
    labelKey: "provenance.confirmed",
  },
  doctor: {
    icon: Stethoscope,
    chip: "border-ink bg-ink text-white",
    block: "border-ink bg-surface",
    labelKey: "provenance.doctor",
  },
  needsReview: {
    icon: Warning,
    chip: "border-mark-ink/40 bg-mark-soft text-mark-ink",
    block: "border-mark-ink/40 bg-mark-soft",
    labelKey: "provenance.needsReview",
  },
  pending: {
    icon: Clock,
    chip: "border-line bg-sunken text-muted",
    block: "border-line bg-surface",
    labelKey: "provenance.pending",
  },
  rejected: {
    icon: Prohibit,
    chip: "border-line bg-sunken text-subtle",
    block: "border-line bg-sunken",
    labelKey: "provenance.rejected",
  },
  processing: {
    icon: ArrowsClockwise,
    chip: "border-dashed border-ai-line bg-ai-soft text-ai",
    block: "border-dashed border-ai-line bg-ai-soft",
    labelKey: "provenance.processing",
  },
  shared: {
    icon: PaperPlaneTilt,
    chip: "border-line bg-surface text-muted",
    block: "border-line bg-surface",
    labelKey: "provenance.shared",
  },
  failed: {
    icon: WarningCircle,
    chip: "border-danger/35 bg-danger-soft text-danger",
    block: "border-danger/35 bg-danger-soft",
    labelKey: "provenance.failed",
  },
};

export function ProvenanceChip({
  kind,
  label,
  className,
}: {
  kind: ProvenanceKind;
  /** Overrides the default label when a screen has a more precise word for it. */
  label?: ReactNode;
  className?: string;
}) {
  const t = useT();
  const { icon: Glyph, chip, labelKey } = KINDS[kind];
  return (
    <span
      className={cn(
        // A paper tag, not a pill: the corners stay near square like everything else.
        "inline-flex max-w-full items-center gap-1.5 rounded-sm border px-2 py-0.5 text-caption font-semibold",
        chip,
        className,
      )}
    >
      <Glyph size={13} weight="bold" aria-hidden className="shrink-0" />
      {label ?? t(labelKey)}
    </span>
  );
}

/**
 * A block of content whose origin is unmistakable: the edge states it, the chip
 * names it, then the content itself. Used for the patient's words, a page of a
 * document, machine output, and doctor-authored text.
 */
export function ProvenanceBlock({
  kind,
  label,
  meta,
  action,
  children,
  className,
  lang,
}: {
  kind: ProvenanceKind;
  label?: ReactNode;
  /** Language, date, engine — whatever qualifies the source. */
  meta?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  lang?: string;
}) {
  return (
    <div className={cn("rounded-md border px-4 py-3", KINDS[kind].block, className)}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <ProvenanceChip kind={kind} label={label} />
          {meta ? <span className="text-caption text-muted">{meta}</span> : null}
        </div>
        {action}
      </div>
      <div lang={lang} className="text-body text-ink">
        {children}
      </div>
    </div>
  );
}

/** Teaches the fold language once, where a first-time user meets it. */
export function ProvenanceLegend({ className }: { className?: string }) {
  const t = useT();
  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      <span className="text-caption text-muted">{t("provenance.legend")}:</span>
      <ProvenanceChip kind="original" />
      <ProvenanceChip kind="machine" />
      <ProvenanceChip kind="confirmed" />
      <ProvenanceChip kind="doctor" />
    </div>
  );
}
