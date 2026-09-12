"use client";

import { errorMessage, useI18n } from "@carebridge/i18n";
import {
  languageInfo,
  type AIFact,
  type AIFactAction,
  type AIProcessing,
  type NormalizationCheck,
} from "@carebridge/shared-types";
import { Alert, Badge, Button, Card, CardHeader, Field, TextInput, cn } from "@carebridge/ui";
import { useState } from "react";

/**
 * Optional AI assistance for one record.
 *
 * The three layers stay visibly separate — 1 the patient's own words (never
 * changed), 2 the English version, 3 the structured items with their evidence —
 * plus whether layer 2 still means what layer 1 said. Nothing reaches the
 * health record until the patient confirms it.
 */
export function AIAssistPanel({
  originalText,
  hasConsent,
  result,
  onGrantConsent,
  onProcess,
  onReviewFact,
}: {
  originalText: string;
  hasConsent: boolean;
  result: AIProcessing | null;
  onGrantConsent: () => Promise<void>;
  onProcess: () => Promise<AIProcessing>;
  onReviewFact: (factId: string, action: AIFactAction) => Promise<AIFact>;
}) {
  const { t, formatDateTime } = useI18n();
  const [current, setCurrent] = useState<AIProcessing | null>(result);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const state = current ?? result;

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

  const process = () => guard(async () => setCurrent(await onProcess()));
  const grant = () => guard(onGrantConsent);

  const review = (factId: string, action: AIFactAction) =>
    guard(async () => {
      const updated = await onReviewFact(factId, action);
      setCurrent((prev) =>
        prev ? { ...prev, facts: prev.facts.map((f) => (f.id === updated.id ? updated : f)) } : prev,
      );
    });

  // The patient's own facts first; anything about a relative after.
  const facts = state ? [...state.facts].sort((a, b) => Number(a.subject !== "self") - Number(b.subject !== "self")) : [];

  return (
    <Card>
      <CardHeader title={t("ai.title")} description={t("ai.subtitle")} />
      <Alert tone="info" className="mb-4">
        {t("ai.notDiagnosis")}
      </Alert>

      {!hasConsent ? (
        <div className="rounded-lg border border-dashed border-line-strong bg-sunken p-4">
          <p className="font-semibold">{t("ai.consentTitle")}</p>
          <p className="mt-1 text-muted">{t("ai.consentBody")}</p>
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
              {busy ? t("ai.processing") : state ? t("ai.reprocess") : t("ai.process")}
            </Button>
            <Badge tone="success">{t("ai.consentOn")}</Badge>
          </div>
          {error ? (
            <Alert tone="error" className="mt-3">
              {errorMessage(t, error)}
            </Alert>
          ) : null}

          {state?.status === "unavailable" ? (
            <Alert tone="warning" className="mt-4" title={t("ai.unavailableTitle")}>
              {t("ai.unavailable")}
            </Alert>
          ) : null}

          {state?.status === "ok" ? (
            <div className="mt-5 flex flex-col gap-5">
              <section aria-label={t("ai.layers.original")}>
                <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">{t("ai.layers.original")}</h3>
                <p
                  lang={state.detected_language ?? undefined}
                  className="mt-1 whitespace-pre-line rounded-lg bg-sunken px-3.5 py-2.5"
                >
                  {state.original_text ?? originalText}
                </p>
              </section>

              <section aria-label={t("ai.layers.normalized")}>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">
                    {t("ai.layers.normalized")}
                  </h3>
                  <Badge tone="ai">{t("ai.machineGenerated")}</Badge>
                  {state.detected_language ? (
                    <span className="text-sm text-muted">
                      {t("ai.detectedLanguage", {
                        language: languageInfo(state.detected_language)?.nativeName ?? state.detected_language,
                      })}
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 whitespace-pre-line rounded-lg border border-ai/30 bg-ai-soft/40 px-3.5 py-2.5">
                  {state.normalized_english}
                </p>
                {state.unparsed.length > 0 ? (
                  <p className="mt-2 text-sm text-muted">
                    {t("ai.unparsed")}: {state.unparsed.join(" · ")}
                  </p>
                ) : null}
                <div className="mt-2">
                  <MeaningCheck check={state.normalization_check} />
                </div>
              </section>

              <section aria-label={t("ai.layers.facts")}>
                <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">{t("ai.layers.facts")}</h3>
                <p className="mt-1 font-semibold">{t("ai.reviewTitle")}</p>
                <p className="text-sm text-muted">{t("ai.reviewSubtitle")}</p>
                {facts.length === 0 ? (
                  <p className="mt-3 text-muted">{t("ai.noFacts")}</p>
                ) : (
                  <ul className="mt-3 flex flex-col gap-2">
                    {facts.map((fact) => (
                      <FactRow key={fact.id} fact={fact} busy={busy} onReview={review} />
                    ))}
                  </ul>
                )}
              </section>

              <p className="text-xs text-subtle">
                {t("ai.provenance", { provider: state.provider ?? "", model: state.model ?? "" })}
                {state.generated_at ? ` · ${t("ai.generatedOn", { date: formatDateTime(state.generated_at) })}` : ""}
                {state.runs.some((r) => r.cached) ? ` · ${t("ai.cached")}` : ""}
              </p>
            </div>
          ) : null}
        </>
      )}
    </Card>
  );
}

/** Whether the English version still means what the patient wrote. */
export function MeaningCheck({ check }: { check: NormalizationCheck | null }) {
  const { t } = useI18n();
  if (!check) return null;
  if (check.status === "ok") return <Badge tone="success">{t("ai.check.ok")}</Badge>;
  return (
    <Alert tone="warning" title={t("ai.check.review")}>
      {check.added_terms.length > 0 ? (
        <p>
          {t("ai.check.added")}: {check.added_terms.join(", ")}
        </p>
      ) : null}
      {check.dropped_facts.length > 0 ? (
        <p>
          {t("ai.check.dropped")}: {check.dropped_facts.join(", ")}
        </p>
      ) : null}
      {check.notes.includes("attribution_lost") ? <p>{t("ai.check.attributionLost")}</p> : null}
    </Alert>
  );
}

export function FactRow({
  fact,
  busy,
  onReview,
  onShowEvidence,
  highlighted = false,
}: {
  fact: AIFact;
  busy: boolean;
  onReview: (factId: string, action: AIFactAction) => Promise<void>;
  /** Documents: point at the evidence on the page image. */
  onShowEvidence?: (fact: AIFact) => void;
  highlighted?: boolean;
}) {
  const { t } = useI18n();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(fact.effective_value);
  const aboutSomeoneElse = fact.subject !== "self";
  const page = fact.evidence_page_number ?? null;

  const stateBadge = {
    pending: <Badge tone="warning">{t("ai.pendingReview")}</Badge>,
    confirmed: <Badge tone="success">{t("ai.confirmedByPatient")}</Badge>,
    edited: <Badge tone="success">{t("ai.editedByPatient")}</Badge>,
    rejected: <Badge tone="danger">{t("ai.reject")}</Badge>,
  }[fact.review_state];

  return (
    <li
      className={cn(
        "rounded-lg border px-3.5 py-3",
        highlighted && "ring-2 ring-ai",
        fact.review_state === "rejected"
          ? "border-line bg-sunken opacity-60"
          : aboutSomeoneElse
            ? "border-warning/40 bg-warning-soft/40"
            : "border-line bg-surface",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">
              {t(`ai.category.${fact.category}`)}
            </p>
            <Badge tone={aboutSomeoneElse ? "warning" : "neutral"}>{t(`ai.subject.${fact.subject}`)}</Badge>
          </div>
          {editing ? (
            <Field label={t("ai.editLabel")} className="mt-1">
              {(p) => (
                <TextInput {...p} value={draft} maxLength={300} onChange={(e) => setDraft(e.target.value)} />
              )}
            </Field>
          ) : (
            <p className="font-semibold">{fact.effective_value}</p>
          )}
          <p className="mt-1 text-sm text-muted">
            <span className="font-medium">{t("ai.evidenceFrom")}: </span>
            <q>{fact.evidence_quote}</q>
          </p>
          {page !== null ? (
            <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted">
              <span>{t("docAi.onPage", { page })}</span>
              {onShowEvidence && fact.evidence_bbox ? (
                <Button variant="ghost" size="sm" aria-pressed={highlighted} onClick={() => onShowEvidence(fact)}>
                  {t("docAi.showOnPage")}
                </Button>
              ) : null}
            </p>
          ) : null}
          {fact.subject_evidence ? (
            <p className="mt-0.5 text-sm text-muted">{t("ai.attributedTo", { cue: fact.subject_evidence })}</p>
          ) : null}
          {fact.subject === "family" ? (
            <p className="mt-1 text-sm font-medium text-warning">{t("ai.familyNotYours")}</p>
          ) : null}
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {stateBadge}
            {fact.validation_status === "needs_review" ? <Badge tone="warning">{t("ai.needsReview")}</Badge> : null}
            {fact.medical_record_id ? <Badge tone="info">{t("ai.addedToRecord")}</Badge> : null}
          </div>
        </div>
        <div className="flex flex-wrap gap-1">
          {editing ? (
            <>
              <Button
                size="sm"
                disabled={busy || !draft.trim()}
                onClick={async () => {
                  await onReview(fact.id, { action: "edit", value: draft.trim() });
                  setEditing(false);
                }}
              >
                {t("actions.save")}
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>
                {t("actions.cancel")}
              </Button>
            </>
          ) : (
            <>
              <Button
                size="sm"
                variant="secondary"
                disabled={busy || fact.review_state === "confirmed"}
                onClick={() => onReview(fact.id, { action: "confirm" })}
              >
                {t("ai.confirm")}
              </Button>
              <Button variant="ghost" size="sm" disabled={busy} onClick={() => setEditing(true)}>
                {t("ai.edit")}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="text-danger hover:bg-danger-soft"
                disabled={busy || fact.review_state === "rejected"}
                onClick={() => onReview(fact.id, { action: "reject" })}
              >
                {t("ai.reject")}
              </Button>
            </>
          )}
        </div>
      </div>
    </li>
  );
}
