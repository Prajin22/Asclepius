"use client";

import { errorMessage, useI18n } from "@carebridge/i18n";
import {
  languageInfo,
  type AIFact,
  type AIFactAction,
  type DocumentPage,
  type DocumentProcessing,
} from "@carebridge/shared-types";
import {
  Alert,
  Button,
  Card,
  CardHeader,
  EmptyState,
  FoldTrack,
  Mark,
  PageImage,
  ProvenanceBlock,
  ProvenanceChip,
  ReadingProvenance,
  cn,
} from "@carebridge/ui";
import { BookOpenText, Lock } from "@phosphor-icons/react/dist/ssr";
import { useState } from "react";
import { FactRow, LayerLabel, MeaningCheck } from "./AIAssistPanel";

/**
 * Reading an uploaded document, page by page.
 *
 * The original file is never changed and stays on screen at a size worth reading.
 * For each page the layers stay separate and registered against it: 1 the text read
 * from the page (an exact copy or a machine transcription, labelled as such), 2 its
 * English version, 3 the items found, each pointing at where its evidence sits. On a
 * wide screen the page is pinned while the items scroll beside it; on a phone they
 * stack, page first.
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
  const pending = pages.reduce((n, p) => n + p.facts.filter((f) => f.review_state === "pending").length, 0);

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

  // Four folds: the page itself, the text read from it, what was made of that, your check.
  const steps = [
    { key: "original", label: t("docAi.steps.original") },
    { key: "reading", label: t("docAi.steps.reading") },
    { key: "organised", label: t("docAi.steps.organised") },
    { key: "review", label: t("docAi.steps.review") },
  ];
  const step = !extraction ? "original" : page?.ai_status !== "ok" ? "reading" : pending > 0 ? "review" : "organised";

  return (
    <Card aria-labelledby="doc-reading-heading">
      <CardHeader
        id="doc-reading-heading"
        title={t("docAi.title")}
        description={t("docAi.subtitle")}
        action={<ProvenanceChip kind="machine" />}
      />
      {/* Said once, quietly, where the machine's output actually appears. */}
      <p className="text-small text-muted">{t("ai.notDiagnosis")}</p>
      <p className="mb-4 text-small text-muted">{t("docAi.originalStays")}</p>

      {!hasConsent ? (
        <div className="rounded-md border border-dashed border-line-strong bg-sunken/70 p-5">
          <Lock size={22} weight="regular" aria-hidden className="text-brand" />
          <p className="mt-2 text-subheading text-ink">{t("ai.consentTitle")}</p>
          <p className="mt-1 text-body text-muted">{t("docAi.consentBody")}</p>
          <p className="mt-1 text-small text-subtle">{t("ai.consentExternalNote")}</p>
          {error ? (
            <Alert tone="error" className="mt-3">
              {errorMessage(t, error)}
            </Alert>
          ) : null}
          <Button className="mt-4" size="lg" loading={busy} onClick={grant}>
            {t("ai.enable")}
          </Button>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <Button size="lg" loading={busy} onClick={process}>
              <BookOpenText size={18} weight="regular" aria-hidden />
              {busy ? t("docAi.reading") : state && state.status !== "not_processed" ? t("docAi.readAgain") : t("docAi.read")}
            </Button>
            <span className="text-small text-muted">{t("ai.consentOn")}</span>
            {pending > 0 ? <Mark label={t("ai.pendingCount", { count: pending })} /> : null}
          </div>
          {error ? (
            <Alert tone="error" className="mt-3">
              {errorMessage(t, error)}
            </Alert>
          ) : null}

          {!state || state.status === "not_processed" ? (
            <EmptyState className="mt-4" title={t("docAi.notRead")}>
              {t("docAi.notReadWhy")}
            </EmptyState>
          ) : null}
          {state?.status === "failed" ? (
            <Alert tone="warning" className="mt-4" title={state.error_code === "no_text_found" ? t("docAi.noText") : t("docAi.failed")}>
              {t("docAi.originalSafe")}
            </Alert>
          ) : null}

          {extraction && page ? (
            <div className="mt-5 flex flex-col gap-4">
              <FoldTrack inline steps={steps} current={step} label={t("docAi.stepsLabel")} />

              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-small text-muted">
                <span>{t("docAi.summary", { processed: extraction.pages_processed, total: extraction.page_count })}</span>
                {extraction.truncated ? (
                  <span className="font-medium text-warning">
                    {t("reading.warnings.truncated", { count: extraction.pages_processed, total: extraction.page_count })}
                  </span>
                ) : null}
              </div>

              {pages.length > 1 ? (
                <nav aria-label={t("docAi.pages")} className="flex gap-5 overflow-x-auto border-b border-line">
                  {pages.map((p) => {
                    const selected = p.page_number === page.page_number;
                    return (
                      <button
                        key={p.page_id}
                        type="button"
                        aria-pressed={selected}
                        onClick={() => showPage(p.page_number)}
                        className={cn(
                          "-mb-px inline-flex min-h-11 shrink-0 items-center border-b-2 text-small font-semibold transition-colors duration-150 sm:min-h-10",
                          selected ? "border-ink text-ink" : "border-transparent text-muted hover:text-ink",
                        )}
                      >
                        {t("docAi.pageTitle", { page: p.page_number })}
                      </button>
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
      className="grid gap-5 xl:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]"
    >
      {/* The original page, pinned, with the evidence outlined on it. */}
      <div className="min-w-0">
        <div className="xl:sticky xl:top-24">
          <PageImage load={() => loadPage(page.page_number)} page={page.page_number} regions={regions} />
          <p className="mt-2 text-caption text-subtle">
            {t("provenance.document")} · {t("docAi.pageTitle", { page: page.page_number })}
          </p>
        </div>
      </div>

      <div className="flex min-w-0 flex-col gap-4">
        <section aria-label={t("docAi.layers.read")}>
          <LayerLabel label={t("docAi.layers.read")} />
          <div className="mt-1.5">
            <ReadingProvenance
              method={page.method}
              engine={page.engine}
              confidence={page.confidence}
              warnings={page.warnings}
            />
          </div>
          {page.text.trim() ? (
            <ProvenanceBlock kind="document" className="mt-2" lang={page.detected_language ?? undefined}>
              <p tabIndex={0} className="max-h-72 overflow-auto whitespace-pre-line font-mono text-small leading-relaxed">
                {page.text}
              </p>
            </ProvenanceBlock>
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
              <LayerLabel label={t("docAi.layers.english")} />
              <ProvenanceBlock
                kind="machine"
                className="mt-1.5"
                label={t("ai.machineGenerated")}
                meta={
                  page.detected_language
                    ? t("ai.detectedLanguage", {
                        language: languageInfo(page.detected_language)?.nativeName ?? page.detected_language,
                      })
                    : undefined
                }
              >
                <p className="whitespace-pre-line">{page.normalized_english}</p>
                <div className="mt-3">
                  <MeaningCheck check={page.normalization_check} />
                </div>
              </ProvenanceBlock>
            </section>

            <section aria-label={t("docAi.layers.items")}>
              <LayerLabel label={t("docAi.layers.items")} />
              <p className="mt-1.5 text-subheading text-ink">{t("docAi.reviewTitle")}</p>
              <p className="text-small text-muted">{t("docAi.reviewSubtitle")}</p>
              {facts.length === 0 ? (
                <p className="mt-3 rounded-md border border-dashed border-line-strong bg-sunken/70 px-4 py-5 text-center text-muted">
                  {t("docAi.noItems")}
                </p>
              ) : (
                <ul className="mt-3 flex flex-col gap-2.5">
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

            {/* Provider and model are developer material, not a patient's reading.
                Named apart from the page's reading disclosure, so one page never
                offers two toggles with the same words. */}
            <details className="text-caption text-subtle">
              <summary className="inline-flex min-h-8 cursor-pointer items-center hover:text-muted">
                {t("ai.providerDetails")}
              </summary>
              <p className="mt-0.5">
                {provider ? t("ai.provenance", { provider, model: model ?? "" }) : ""}
                {page.generated_at ? ` · ${t("ai.generatedOn", { date: formatDateTime(page.generated_at) })}` : ""}
              </p>
            </details>
          </>
        ) : null}
      </div>
    </section>
  );
}
