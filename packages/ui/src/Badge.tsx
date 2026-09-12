"use client";

import { useT } from "@carebridge/i18n";
import { languageInfo, type ConsultationStatus, type LanguageCode, type RecordSource } from "@carebridge/shared-types";
import type { ReactNode } from "react";
import { cn } from "./cn";

export type Tone = "neutral" | "brand" | "info" | "success" | "warning" | "danger" | "ai";

const tones: Record<Tone, string> = {
  neutral: "border-line bg-sunken text-muted",
  brand: "border-brand/25 bg-brand-soft text-brand-strong",
  info: "border-info/25 bg-info-soft text-info",
  success: "border-success/25 bg-success-soft text-success",
  warning: "border-warning/25 bg-warning-soft text-warning",
  danger: "border-danger/25 bg-danger-soft text-danger",
  ai: "border-dashed border-ai/40 bg-ai-soft text-ai",
};

export function Badge({ tone = "neutral", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

const statusTone: Record<ConsultationStatus, Tone> = {
  requested: "warning",
  accepted: "info",
  active: "success",
  completed: "neutral",
  cancelled: "danger",
};

export function StatusBadge({ status }: { status: ConsultationStatus }) {
  const t = useT();
  return <Badge tone={statusTone[status]}>{t(`status.${status}`)}</Badge>;
}

const sourceTone: Record<RecordSource, Tone> = { patient: "info", ai_extracted: "ai", doctor: "brand" };

function SourceIcon({ source }: { source: RecordSource }) {
  const common = { width: 12, height: 12, viewBox: "0 0 12 12", "aria-hidden": true, focusable: false } as const;
  if (source === "doctor")
    return (
      <svg {...common}>
        <path d="M4.5 1h3v3.5H11v3H7.5V11h-3V7.5H1v-3h3.5z" fill="currentColor" />
      </svg>
    );
  if (source === "ai_extracted")
    return (
      <svg {...common}>
        <path d="M6 0.8 7.4 4.6 11.2 6 7.4 7.4 6 11.2 4.6 7.4 0.8 6 4.6 4.6z" fill="currentColor" />
      </svg>
    );
  return (
    <svg {...common}>
      <circle cx="6" cy="3.6" r="2.4" fill="currentColor" />
      <path d="M1.5 11c0-2.6 2-4.2 4.5-4.2s4.5 1.6 4.5 4.2z" fill="currentColor" />
    </svg>
  );
}

/** Makes the origin of every piece of health information explicit. */
export function SourceBadge({ source }: { source: RecordSource }) {
  const t = useT();
  return (
    <Badge tone={sourceTone[source]}>
      <SourceIcon source={source} />
      {t(`source.${source}`)}
    </Badge>
  );
}

/** Language autonym, tagged with `lang` so screen readers pronounce it correctly. */
export function LanguageTag({ code, className }: { code: LanguageCode | null | undefined; className?: string }) {
  const info = languageInfo(code);
  if (!info) return null;
  return (
    <span lang={info.code} className={cn("text-xs font-medium text-muted", className)}>
      {info.nativeName}
    </span>
  );
}
