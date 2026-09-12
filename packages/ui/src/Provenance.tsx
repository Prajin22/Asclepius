"use client";

import { useT } from "@carebridge/i18n";
import { CheckCircle, Clock, FileText, Prohibit, Quotes, Scan, Stethoscope, Warning } from "@phosphor-icons/react/dist/ssr";
import type { ReactNode } from "react";
import { cn } from "./cn";

/** Every Phosphor glyph shares one component type; derive it rather than import it. */
type Glyph = typeof CheckCircle;

/**
 * Where a piece of information came from — the product's strongest principle.
 *
 * Source is carried by three things at once, never colour alone: a rule down the
 * left edge (solid for human, dashed for machine), an icon, and a label. Original
 * material sits on paper, machine output on steel, human decisions in jade.
 */
export type ProvenanceKind =
  | "original"
  | "document"
  | "machine"
  | "confirmed"
  | "doctor"
  | "needsReview"
  | "pending"
  | "rejected";

const KINDS: Record<ProvenanceKind, { icon: Glyph; chip: string; block: string; labelKey: string }> = {
  original: {
    icon: Quotes,
    chip: "border-paper-line bg-paper text-paper-ink",
    block: "border-l-[3px] border-l-paper-line bg-paper",
    labelKey: "provenance.original",
  },
  document: {
    icon: FileText,
    chip: "border-paper-line bg-paper text-paper-ink",
    block: "border-l-[3px] border-l-paper-line bg-paper",
    labelKey: "provenance.document",
  },
  machine: {
    icon: Scan,
    chip: "border-dashed border-ai-line bg-ai-soft text-ai",
    block: "border-l-[3px] border-dashed border-l-ai-line bg-ai-soft",
    labelKey: "provenance.machine",
  },
  confirmed: {
    icon: CheckCircle,
    chip: "border-brand/25 bg-brand-soft text-brand-strong",
    block: "border-l-[3px] border-l-brand bg-brand-tint",
    labelKey: "provenance.confirmed",
  },
  doctor: {
    icon: Stethoscope,
    chip: "border-ink/20 bg-ink/[0.06] text-ink",
    block: "border-l-[3px] border-l-ink bg-surface",
    labelKey: "provenance.doctor",
  },
  needsReview: {
    icon: Warning,
    chip: "border-warning/30 bg-warning-soft text-warning",
    block: "border-l-[3px] border-l-warning bg-warning-soft",
    labelKey: "provenance.needsReview",
  },
  pending: {
    icon: Clock,
    chip: "border-line bg-sunken text-muted",
    block: "border-l-[3px] border-l-line-strong bg-surface",
    labelKey: "provenance.pending",
  },
  rejected: {
    icon: Prohibit,
    chip: "border-line bg-sunken text-subtle",
    block: "border-l-[3px] border-l-line-strong bg-sunken",
    labelKey: "provenance.rejected",
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
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-caption font-semibold",
        chip,
        className,
      )}
    >
      <Glyph size={13} weight="bold" aria-hidden />
      {label ?? t(labelKey)}
    </span>
  );
}

/**
 * A block of content whose origin is unmistakable: ruled edge, chip, then the
 * content itself. Used for the patient's words, a page of a document, machine
 * output, and doctor-authored text.
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
    <div className={cn("rounded-lg border border-line py-3 pl-4 pr-3.5", KINDS[kind].block, className)}>
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

/** Explains the four sources once, where a first-time user meets them. */
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
