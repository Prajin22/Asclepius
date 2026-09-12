"use client";

import { errorMessage, useI18n } from "@carebridge/i18n";
import {
  languageInfo,
  type AIFact,
  type AIFactAction,
  type DocumentPage,
  type DocumentProcessing,
} from "@carebridge/shared-types";
import { Alert, Badge, Button, Card, CardHeader, PageImage, ReadingProvenance } from "@carebridge/ui";
import { useState } from "react";
import { FactRow, MeaningCheck } from "./AIAssistPanel";

/**
 * Reading an uploaded document, page by page.
 *
 * The original file is never changed and stays on screen. For each page the
 * three layers stay separate — 1 the text read from the page (an exact copy or a
 * machine transcription, labelled as such), 2 its English version, 3 the items
 * found, each pointing at where its evidence sits on the page. Nothing reaches
 * the health record until the patient confirms it.
 */
export function DocumentReadingPanel({
  hasConsent,
  result,
  onGrantConsent,
  onProcess,
  onReviewFact,
  loadPage,
}: {
  hasConsent: boolean;
  result: DocumentProcessing | null;
  onGrantConsent: () => Promise<void>;
  onProcess: () => Promise<DocumentProcessing>;
  onReviewFact: (factId: string, action: AIFactAction) => Promise<AIFact>;
  loadPage: (page: number) => Promise<Blob>;
}) {
  const { t } = useI18n();
  const [current, setCurrent] = useState<DocumentProcessing | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [pageNumber, setPageNumber] = useState<number | null>(null);
  const [highlighted, setHighlighted] = useState<string | null>(null);

  const state = current ?? result;
  const pages = state?.pages ?? [];
  const page = pages.find((p) => p.page_number === pageNumber) ?? pages[0] ?? null;
  const extraction = state?.extraction ?? null;

  async function guard(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const process = () =>
    guard(async () => {
      setCurrent(await onProcess());
      setHighlighted(null);
    });
  const grant = () => guard(onGrantConsent);

  const review = (factId: string, action: AIFactAction) =>
    guard(async () => {
      const updated = await onReviewFact(factId, action);
      const base = current ?? result;
      if (!base) return;
      setCurrent({
        ...base,
        pages: base.pages.map((p) => ({ ...p, facts: p.facts.map((f) => (f.id === updated.id ? updated : f)) })),
      });
    });

  const showPage = (n: number) => {
    setPageNumber(n);
    setHighlighted(null);
  };

  return (
    <Card>
      <CardHeader title={t("docAi.title")} description={t("docAi.subtitle")} />
      <Alert tone="info" className="mb-3">
        {t("ai.notDiagnosis")}
      </Alert>
      <p className="mb-4 text-sm text-muted">{t("docAi.originalStays")}</p>

      {!hasConsent ? (
        <div className="rounded-lg border border-dashed border-line-strong bg-sunken p-4">
          <p className="font-semibold">{t("ai.consentTitle")}</p>
          <p className="mt-1 text-muted">{t("docAi.consentBody")}</p>
          <p className="mt-1 text-sm text-muted">{t("ai.consentExternalNote")}</p>
          {error ? (
            <Alert tone="error" className="mt-3">
              {errorMessage(t, error)}
            </Alert>
          ) : null}
          <Button className="mt-3" size="lg" disabled={busy} onClick={grant}>
            {t("ai.enable")}
          </Button>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <Button size="lg" disabled={busy} onClick={process}>
              {busy
                ? t("docAi.reading")
                : state && state.status !== "not_processed"
                  ? t("docAi.readAgain")
                  : t("docAi.read")}
            </Button>
            <Badge tone="success">{t("ai.consentOn")}</Badge>
          </div>
          {error ? (
            <Alert tone="error" className="mt-3">
              {errorMessage(t, error)}
            </Alert>
          ) : null}

          {!state || state.status === "not_processed" ? <p className="mt-4 text-muted">{t("docAi.notRead")}</p> : null}
          {state?.status === "failed" ? (
            <Alert tone="warning" className="mt-4">
              {state.error_code === "no_text_found" ? t("docAi.noText") : t("docAi.failed")}
            </Alert>
          ) : null}

          {extraction && page ? (
            <div className="mt-5 flex flex-col gap-4">
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
                <span>{t("docAi.summary", { processed: extraction.pages_processed, total: extraction.page_count })}</span>
                {extraction.truncated ? (
                  <span className="font-medium text-warning">
                    {t("reading.warnings.truncated", { count: extraction.pages_processed, total: extraction.page_count })}
                  </span>
                ) : null}
              </div>

              {pages.length > 1 ? (
                <nav aria-label={t("docAi.pages")} className="flex flex-wrap gap-1.5">
                  {pages.map((p) => {
                    const selected = p.page_number === page.page_number;
                    return (
                      <Button
                        key={p.page_id}
                        size="sm"
                        variant={selected ? undefined : "secondary"}
                        aria-pressed={selected}
                        onClick={() => showPage(p.page_number)}
                      >
                        {t("docAi.pageTitle", { page: p.page_number })}
                      </Button>
                    );
                  })}
                </nav>
              ) : null}

              <PageView
                page={page}
                busy={busy}
                highlighted={highlighted}
                loadPage={loadPage}
                onReview={review}
                onHighlight={(id) => setHighlighted((cur) => (cur === id ? null : id))}
                provider={state?.provider ?? null}
                model={state?.model ?? null}
              />
            </div>
          ) : null}
        </>
      )}
    </Card>
  );
}

function PageView({
  page,
  busy,
  highlighted,
  loadPage,
  onReview,
  onHighlight,
  provider,
  model,
}: {
  page: DocumentPage;
  busy: boolean;
  highlighted: string | null;
  loadPage: (page: number) => Promise<Blob>;
  onReview: (factId: string, action: AIFactAction) => Promise<void>;
  onHighlight: (factId: string) => void;
  provider: string | null;
  model: string | null;
}) {
  const { t, formatDateTime } = useI18n();
  // The patient's own items first; anything about a relative after.
  const facts = [...page.facts].sort((a, b) => Number(a.subject !== "self") - Number(b.subject !== "self"));
  const regions = page.facts
    .filter((f) => f.evidence_bbox && f.review_state !== "rejected")
    .map((f) => ({ id: f.id, bbox: f.evidence_bbox!, active: f.id === highlighted }));

  return (
    <section
      aria-label={t("docAi.pageTitle", { page: page.page_number })}
      className="grid gap-5 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]"
    >
      <div className="min-w-0">
        <PageImage load={() => loadPage(page.page_number)} page={page.page_number} regions={regions} />
      </div>

      <div className="flex min-w-0 flex-col gap-5">
        <section aria-label={t("docAi.layers.read")}>
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">{t("docAi.layers.read")}</h3>
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
              className="mt-2 max-h-80 overflow-auto whitespace-pre-line rounded-lg bg-sunken px-3.5 py-2.5 text-sm"
            >
              {page.text}
            </p>
          ) : (
            <p className="mt-2 text-muted">{t("reading.noText")}</p>
          )}
        </section>

        {page.ai_status === "unavailable" ? (
          <Alert tone="warning" title={t("ai.unavailableTitle")}>
            {t("docAi.pageAi")}
          </Alert>
        ) : null}

        {page.ai_status === "ok" ? (
          <>
            <section aria-label={t("docAi.layers.english")}>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">{t("docAi.layers.english")}</h3>
                <Badge tone="ai">{t("ai.machineGenerated")}</Badge>
                {page.detected_language ? (
                  <span className="text-sm text-muted">
                    {t("ai.detectedLanguage", {
                      language: languageInfo(page.detected_language)?.nativeName ?? page.detected_language,
                    })}
                  </span>
                ) : null}
              </div>
              <p className="mt-1 whitespace-pre-line rounded-lg border border-ai/30 bg-ai-soft/40 px-3.5 py-2.5 text-sm">
                {page.normalized_english}
              </p>
              <div className="mt-2">
                <MeaningCheck check={page.normalization_check} />
              </div>
            </section>

            <section aria-label={t("docAi.layers.items")}>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">{t("docAi.layers.items")}</h3>
              <p className="mt-1 font-semibold">{t("docAi.reviewTitle")}</p>
              <p className="text-sm text-muted">{t("docAi.reviewSubtitle")}</p>
              {facts.length === 0 ? (
                <p className="mt-3 text-muted">{t("docAi.noItems")}</p>
              ) : (
                <ul className="mt-3 flex flex-col gap-2">
                  {facts.map((fact) => (
                    <FactRow
                      key={fact.id}
                      fact={fact}
                      busy={busy}
                      onReview={onReview}
                      highlighted={fact.id === highlighted}
                      onShowEvidence={(f) => onHighlight(f.id)}
                    />
                  ))}
                </ul>
              )}
            </section>
          </>
        ) : null}

        {provider ? (
          <p className="text-xs text-subtle">
            {t("ai.provenance", { provider, model: model ?? "" })}
            {page.generated_at ? ` · ${t("ai.generatedOn", { date: formatDateTime(page.generated_at) })}` : ""}
          </p>
        ) : null}
      </div>
    </section>
  );
}
