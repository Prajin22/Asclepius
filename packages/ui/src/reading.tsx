"use client";

import { useT } from "@carebridge/i18n";
import { Badge } from "./Badge";

const WARNING_KEYS: Record<string, string> = {
  low_ocr_confidence: "reading.warnings.lowConfidence",
  no_text_detected: "reading.warnings.noTextDetected",
  no_text_layer_and_ocr_unavailable: "reading.warnings.ocrUnavailable",
  vision_has_no_line_positions: "reading.warnings.noPositions",
  vision_reported_unreadable_regions: "reading.warnings.unreadableRegions",
};

/** Localisation key for a page-reading warning code from the API, or null if it has no page-level message. */
export function readingWarningKey(code: string): string | null {
  if (code.startsWith("vision_failed:")) return "reading.warnings.failed";
  return WARNING_KEYS[code] ?? null;
}

/**
 * How a page's text was obtained. An exact copy and a machine transcription are
 * labelled differently on purpose, with OCR confidence and warnings beside them.
 */
export function ReadingProvenance({
  method,
  engine,
  confidence,
  warnings = [],
}: {
  method: string;
  engine: string;
  confidence: number | null;
  warnings?: string[];
}) {
  const t = useT();
  const exact = method === "pdf_text_layer";
  const messages = Array.from(new Set(warnings.map(readingWarningKey).filter((key): key is string => key !== null)));
  return (
    <div className="flex flex-col gap-1.5">
      <p className="flex flex-wrap items-center gap-2 text-sm text-muted">
        <Badge tone={exact ? "neutral" : "warning"}>{t(`reading.method.${method}`)}</Badge>
        {confidence !== null ? <span>{t("reading.confidence", { percent: Math.round(confidence * 100) })}</span> : null}
        <span className="text-xs text-subtle">{t("reading.engine", { engine })}</span>
      </p>
      {messages.map((key) => (
        <p key={key} className="text-sm font-medium text-warning">
          {t(key)}
        </p>
      ))}
    </div>
  );
}
