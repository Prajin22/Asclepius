"use client";

import { useI18n } from "@carebridge/i18n";
import type { AIFactSummary, DocumentInsight as DocumentInsightData } from "@carebridge/shared-types";
import { Badge, Button, PageImage, ReadingProvenance } from "@carebridge/ui";
import { useState } from "react";
import { FactList } from "@/components/AIInsight";

/**
 * Machine reading of a shared document, shown beside the original file — never
 * instead of it. Collapsed by default. When opened, one page at a time: the page
 * image with evidence outlined, the text read from it (labelled as an exact copy
 * or a machine transcription), its English version, and the extracted items with
 * attribution and the patient's confirmation status. What any of it means
 * clinically is the doctor's decision.
 */
export function DocumentInsight({
  insight,
  loadPage,
}: {
  insight: DocumentInsightData;
  loadPage?: (page: number) => Promise<Blob>;
}) {
  const { t, formatDateTime } = useI18n();
  const [open, setOpen] = useState(false);
  const [pageNumber, setPageNumber] = useState<number | null>(null);
  const [active, setActive] = useState<AIFactSummary | null>(null);

  const failed = insight.extraction_status === "failed";
  const page = insight.pages.find((p) => p.page_number === pageNumber) ?? insight.pages[0] ?? null;
  const aboutRelatives = insight.pages.some((p) => p.facts.some((f) => f.subject !== "self"));
  const own = page ? page.facts.filter((f) => f.subject === "self") : [];
  const others = page ? page.facts.filter((f) => f.subject !== "self") : [];
  const regions = page
    ? page.facts
        .filter((f) => f.evidence_bbox)
        .map((f, index) => ({ id: `${page.page_number}-${index}`, bbox: f.evidence_bbox!, active: f === active }))
    : [];
  const check = page?.normalization_check ?? null;
  const toggle = loadPage ? (fact: AIFactSummary) => setActive((cur) => (cur === fact ? null : fact)) : undefined;

  return (
    <div className="mt-3 rounded-lg border border-dashed border-ai/40 bg-ai-soft/30">
      <div className="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="ai">{t("docAi.title")}</Badge>
          <span className="text-sm text-muted">
            {failed
              ? t("docAi.failed")
              : t("docAi.summary", { processed: insight.pages_processed, total: insight.page_count })}
          </span>
          {insight.extraction_status === "partial" ? <Badge tone="warning">{t("docAi.partial")}</Badge> : null}
          {aboutRelatives ? <Badge tone="warning">{t("ai.view.subject.family")}</Badge> : null}
        </div>
        {!failed && page ? (
          <Button variant="ghost" size="sm" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
            {open ? t("docAi.hide") : t("docAi.show")}
          </Button>
        ) : null}
      </div>

      {open && page ? (
        <div className="flex flex-col gap-4 border-t border-ai/30 px-3.5 py-3">
          <p className="text-sm text-muted">{t("docAi.subtitle")}</p>
          {insight.truncated ? (
            <p className="text-sm font-medium text-warning">
              {t("reading.warnings.truncated", { count: insight.pages_processed, total: insight.page_count })}
            </p>
          ) : null}

          {insight.pages.length > 1 ? (
            <nav aria-label={t("docAi.pages")} className="flex flex-wrap gap-1.5">
              {insight.pages.map((p) => {
                const selected = p.page_number === page.page_number;
                return (
                  <Button
                    key={p.page_number}
                    size="sm"
                    variant={selected ? undefined : "secondary"}
                    aria-pressed={selected}
                    onClick={() => {
                      setPageNumber(p.page_number);
                      setActive(null);
                    }}
                  >
                    {t("docAi.pageTitle", { page: p.page_number })}
                  </Button>
                );
              })}
            </nav>
          ) : null}

          <div className="grid gap-4 lg:grid-cols-2">
            {loadPage ? (
              <PageImage load={() => loadPage(page.page_number)} page={page.page_number} regions={regions} />
            ) : null}
            <div className="flex min-w-0 flex-col gap-3">
              <section>
                <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">{t("docAi.rawText")}</h4>
                <div className="mt-1">
                  <ReadingProvenance
                    method={page.method}
                    engine={page.engine}
                    confidence={page.confidence}
                    warnings={page.warnings}
                  />
                </div>
                {page.text.trim() ? (
                  <p
                    lang={page.detected_language ?? undefined}
                    className="mt-1 max-h-72 overflow-auto whitespace-pre-line rounded-md bg-surface px-3 py-2 text-sm"
                  >
                    {page.text}
                  </p>
                ) : (
                  <p className="mt-1 text-sm text-muted">{t("reading.noText")}</p>
                )}
              </section>

              {page.ai_status === "ok" ? (
                <section>
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">{t("docAi.english")}</h4>
                  <p className="mt-1 whitespace-pre-line rounded-md border border-ai/30 bg-surface px-3 py-2 text-sm">
                    {page.normalized_english}
                  </p>
                  {check ? (
                    check.status === "ok" ? (
                      <p className="mt-1 text-sm text-success">{t("ai.view.checkOk")}</p>
                    ) : (
                      <p className="mt-1 text-sm font-medium text-warning">{t("ai.view.checkReview")}</p>
                    )
                  ) : null}
                </section>
              ) : page.ai_status === "unavailable" ? (
                <p className="text-sm font-medium text-warning">{t("ai.unavailable")}</p>
              ) : null}
            </div>
          </div>

          <section>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">{t("docAi.items")}</h4>
            {page.facts.length === 0 ? (
              <p className="mt-1 text-sm text-muted">{t("docAi.noItems")}</p>
            ) : (
              <>
                <FactList facts={own} active={active} onShowEvidence={toggle} />
                {others.length > 0 ? (
                  <div className="mt-3">
                    <p className="text-sm font-semibold text-warning">{t("ai.view.familyNote")}</p>
                    <FactList facts={others} active={active} onShowEvidence={toggle} />
                  </div>
                ) : null}
              </>
            )}
          </section>

          <p className="text-xs text-subtle">
            {insight.processed_at ? t("docAi.processedOn", { date: formatDateTime(insight.processed_at) }) : ""}
            {insight.engines.length > 0 ? ` · ${insight.engines.join(", ")}` : ""}
          </p>
        </div>
      ) : null}
    </div>
  );
}
