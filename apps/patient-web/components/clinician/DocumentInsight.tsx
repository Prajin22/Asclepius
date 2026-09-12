"use client";

import { useI18n } from "@carebridge/i18n";
import type { AIFactSummary, DocumentInsight as DocumentInsightData } from "@carebridge/shared-types";
import { Button, PageImage, ProvenanceBlock, ProvenanceChip, ReadingProvenance, cn } from "@carebridge/ui";
import { CaretDown, CaretUp } from "@phosphor-icons/react/dist/ssr";
import { useState } from "react";
import { FactList } from "@/components/clinician/AIInsight";

/**
 * Machine reading of a shared document, shown beside the original file — never
 * instead of it. Collapsed by default. When opened, one page at a time: the page
 * image with evidence outlined, the text read from it (labelled as an exact copy
 * or a machine transcription), its English version, and the extracted items with
 * attribution and the patient's confirmation. What any of it means clinically is
 * the doctor's decision.
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
    <div className="mt-3 rounded-lg border border-dashed border-ai-line bg-ai-soft/60">
      <div className="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <ProvenanceChip kind="machine" label={t("docAi.title")} />
          <span className="text-small text-muted">
            {failed
              ? t("docAi.failed")
              : t("docAi.summary", { processed: insight.pages_processed, total: insight.page_count })}
          </span>
          {insight.extraction_status === "partial" ? (
            <ProvenanceChip kind="needsReview" label={t("docAi.partial")} />
          ) : null}
          {aboutRelatives ? <ProvenanceChip kind="needsReview" label={t("ai.view.subject.family")} /> : null}
        </div>
        {!failed && page ? (
          <Button variant="ghost" size="sm" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
            {open ? <CaretUp size={15} aria-hidden /> : <CaretDown size={15} aria-hidden />}
            {open ? t("docAi.hide") : t("docAi.show")}
          </Button>
        ) : null}
      </div>

      {open && page ? (
        <div className="flex flex-col gap-4 border-t border-ai-line/70 px-3.5 py-3.5">
          <p className="text-small text-muted">{t("docAi.subtitle")}</p>
          {insight.truncated ? (
            <p className="text-small font-medium text-warning">
              {t("reading.warnings.truncated", { count: insight.pages_processed, total: insight.page_count })}
            </p>
          ) : null}

          {insight.pages.length > 1 ? (
            <nav aria-label={t("docAi.pages")} className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1">
              {insight.pages.map((p) => {
                const selected = p.page_number === page.page_number;
                return (
                  <button
                    key={p.page_number}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => {
                      setPageNumber(p.page_number);
                      setActive(null);
                    }}
                    className={cn(
                      "inline-flex min-h-9 shrink-0 items-center rounded-full border px-3.5 text-small font-semibold transition-colors duration-150",
                      selected
                        ? "border-brand bg-brand text-white"
                        : "border-line bg-surface text-muted hover:border-brand/40 hover:text-ink",
                    )}
                  >
                    {t("docAi.pageTitle", { page: p.page_number })}
                  </button>
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
                <h4 className="text-label uppercase text-subtle">{t("docAi.rawText")}</h4>
                <div className="mt-1.5">
                  <ReadingProvenance
                    method={page.method}
                    engine={page.engine}
                    confidence={page.confidence}
                    warnings={page.warnings}
                  />
                </div>
                {page.text.trim() ? (
                  <ProvenanceBlock kind="document" className="mt-2">
                    <p
                      lang={page.detected_language ?? undefined}
                      className="max-h-64 overflow-auto whitespace-pre-line font-mono text-small leading-relaxed"
                    >
                      {page.text}
                    </p>
                  </ProvenanceBlock>
                ) : (
                  <p className="mt-1.5 text-small text-muted">{t("reading.noText")}</p>
                )}
              </section>

              {page.ai_status === "ok" ? (
                <section>
                  <h4 className="text-label uppercase text-subtle">{t("docAi.english")}</h4>
                  <ProvenanceBlock kind="machine" className="mt-1.5">
                    <p className="whitespace-pre-line">{page.normalized_english}</p>
                  </ProvenanceBlock>
                  {check ? (
                    check.status === "ok" ? (
                      <p className="mt-1.5 text-small text-success">{t("ai.view.checkOk")}</p>
                    ) : (
                      <p className="mt-1.5 text-small font-medium text-warning">{t("ai.view.checkReview")}</p>
                    )
                  ) : null}
                </section>
              ) : page.ai_status === "unavailable" ? (
                <p className="text-small font-medium text-warning">{t("ai.unavailable")}</p>
              ) : null}
            </div>
          </div>

          <section>
            <h4 className="text-label uppercase text-subtle">{t("docAi.items")}</h4>
            {page.facts.length === 0 ? (
              <p className="mt-1.5 text-small text-muted">{t("docAi.noItems")}</p>
            ) : (
              <>
                <FactList facts={own} active={active} onShowEvidence={toggle} />
                {others.length > 0 ? (
                  <div className="mt-3">
                    <p className="text-small font-semibold text-warning">{t("ai.view.familyNote")}</p>
                    <FactList facts={others} active={active} onShowEvidence={toggle} />
                  </div>
                ) : null}
              </>
            )}
          </section>

          <p className="text-caption text-subtle">
            {insight.processed_at ? t("docAi.processedOn", { date: formatDateTime(insight.processed_at) }) : ""}
            {insight.engines.length > 0 ? ` · ${insight.engines.join(", ")}` : ""}
          </p>
        </div>
      ) : null}
    </div>
  );
}
