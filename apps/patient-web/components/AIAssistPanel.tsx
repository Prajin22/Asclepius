"use client";

import { errorMessage, useI18n } from "@carebridge/i18n";
import {
  languageInfo,
  type AIFact,
  type AIFactAction,
  type AIProcessing,
  type NormalizationCheck,
} from "@carebridge/shared-types";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  ProvenanceBlock,
  ProvenanceChip,
  TextInput,
  cn,
} from "@carebridge/ui";
import { ArrowDown, CheckCircle, Lock, PencilSimple, Prohibit, Sparkle } from "@phosphor-icons/react/dist/ssr";
import { useState } from "react";

/**
 * Optional AI assistance for one record.
 *
 * The three layers stay visibly separate — 1 the patient's own words (never
 * changed), 2 the English version, 3 the structured items with their evidence —
 * plus whether layer 2 still means what layer 1 said. Nothing reaches the health
 * record until the patient confirms it.
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
    <Card aria-labelledby="ai-panel-heading">
      <CardHeader id="ai-panel-heading" title={t("ai.title")} description={t("ai.subtitle")} />
      <Alert tone="info" className="mb-4">
        {t("ai.notDiagnosis")}
      </Alert>

      {!hasConsent ? (
        <div className="rounded-xl border border-dashed border-line-strong bg-sunken/70 p-5">
          <Lock size={22} weight="regular" aria-hidden className="text-brand" />
          <p className="mt-2 text-subheading text-ink">{t("ai.consentTitle")}</p>
          <p className="mt-1 text-body text-muted">{t("ai.consentBody")}</p>
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
              <Sparkle size={18} weight="regular" aria-hidden />
              {busy ? t("ai.processing") : state ? t("ai.reprocess") : t("ai.process")}
            </Button>
            <Badge tone="success">
              <CheckCircle size={13} weight="bold" aria-hidden />
              {t("ai.consentOn")}
            </Badge>
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
            <div className="mt-5 flex flex-col gap-4">
              <section aria-label={t("ai.layers.original")}>
                <LayerLabel step="1" label={t("ai.layers.original")} />
                <ProvenanceBlock kind="original" lang={state.detected_language ?? undefined} className="mt-2">
                  <p className="whitespace-pre-line text-body-lg">{state.original_text ?? originalText}</p>
                </ProvenanceBlock>
              </section>

              <ArrowDown size={18} aria-hidden className="mx-auto text-subtle" />

              <section aria-label={t("ai.layers.normalized")}>
                <LayerLabel step="2" label={t("ai.layers.normalized")} />
                <ProvenanceBlock
                  kind="machine"
                  className="mt-2"
                  meta={
                    state.detected_language
                      ? t("ai.detectedLanguage", {
                          language: languageInfo(state.detected_language)?.nativeName ?? state.detected_language,
                        })
                      : undefined
                  }
                  label={t("ai.machineGenerated")}
                >
                  <p className="whitespace-pre-line">{state.normalized_english}</p>
                  {state.unparsed.length > 0 ? (
                    <p className="mt-2 text-small text-muted">
                      {t("ai.unparsed")}: {state.unparsed.join(" · ")}
                    </p>
                  ) : null}
                  <div className="mt-3">
                    <MeaningCheck check={state.normalization_check} />
                  </div>
                </ProvenanceBlock>
              </section>

              <ArrowDown size={18} aria-hidden className="mx-auto text-subtle" />

              <section aria-label={t("ai.layers.facts")}>
                <LayerLabel step="3" label={t("ai.layers.facts")} />
                <p className="mt-2 text-subheading text-ink">{t("ai.reviewTitle")}</p>
                <p className="text-small text-muted">{t("ai.reviewSubtitle")}</p>
                {facts.length === 0 ? (
                  <p className="mt-3 rounded-lg border border-dashed border-line-strong bg-sunken/60 px-4 py-5 text-center text-muted">
                    {t("ai.noFacts")}
                  </p>
                ) : (
                  <ul className="mt-3 flex flex-col gap-2.5">
                    {facts.map((fact) => (
                      <FactRow key={fact.id} fact={fact} busy={busy} onReview={review} />
                    ))}
                  </ul>
                )}
              </section>

              <p className="text-caption text-subtle">
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

/** The step number carries the order; the label carries the meaning. */
function LayerLabel({ step, label }: { step: string; label: string }) {
  return (
    <p className="flex items-center gap-2">
      <span className="tabular inline-flex size-6 items-center justify-center rounded-full bg-ink/[0.06] text-caption font-semibold text-ink">
        {step}
      </span>
      <span className="text-label uppercase text-subtle">{label}</span>
    </p>
  );
}

/** Whether the English version still means what the patient wrote. */
export function MeaningCheck({ check }: { check: NormalizationCheck | null }) {
  const { t } = useI18n();
  if (!check) return null;
  if (check.status === "ok")
    return (
      <Badge tone="success">
        <CheckCircle size={13} weight="bold" aria-hidden />
        {t("ai.check.ok")}
      </Badge>
    );
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

const REVIEW_RULE: Record<AIFact["review_state"], string> = {
  pending: "border-l-line-strong",
  confirmed: "border-l-brand",
  edited: "border-l-brand",
  rejected: "border-l-line",
};

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
  const rejected = fact.review_state === "rejected";

  const stateChip = {
    pending: <ProvenanceChip kind="pending" label={t("ai.pendingReview")} />,
    confirmed: <ProvenanceChip kind="confirmed" label={t("ai.confirmedByPatient")} />,
    edited: <ProvenanceChip kind="confirmed" label={t("ai.editedByPatient")} />,
    rejected: <ProvenanceChip kind="rejected" label={t("ai.reject")} />,
  }[fact.review_state];

  return (
    <li
      className={cn(
        "rounded-lg border border-l-[3px] bg-surface px-4 py-3.5 transition-shadow duration-150",
        REVIEW_RULE[fact.review_state],
        rejected ? "border-line bg-sunken/70 opacity-70" : "border-line",
        aboutSomeoneElse && !rejected && "border-warning/40",
        highlighted && "shadow-md ring-2 ring-brand/40",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-label uppercase text-subtle">{t(`ai.category.${fact.category}`)}</span>
            <Badge tone={aboutSomeoneElse ? "warning" : "neutral"}>{t(`ai.subject.${fact.subject}`)}</Badge>
          </div>
          {editing ? (
            <Field label={t("ai.editLabel")} className="mt-2">
              {(p) => <TextInput {...p} value={draft} maxLength={300} onChange={(e) => setDraft(e.target.value)} />}
            </Field>
          ) : (
            <p className={cn("mt-1 text-subheading text-ink", rejected && "line-through decoration-line-strong")}>
              {fact.effective_value}
            </p>
          )}
          <p className="mt-1.5 text-small text-muted">
            <span className="font-medium">{t("ai.evidenceFrom")}: </span>
            <q className="rounded-sm bg-paper px-1 py-0.5 text-paper-ink">{fact.evidence_quote}</q>
          </p>
          {fact.subject_evidence ? (
            <p className="mt-1 text-small text-muted">{t("ai.attributedTo", { cue: fact.subject_evidence })}</p>
          ) : null}
          {fact.subject === "family" ? (
            <p className="mt-1 text-small font-medium text-warning">{t("ai.familyNotYours")}</p>
          ) : null}
          {page !== null ? (
            <p className="mt-1.5 flex flex-wrap items-center gap-2 text-small text-muted">
              <span>{t("docAi.onPage", { page })}</span>
              {onShowEvidence && fact.evidence_bbox ? (
                <Button variant="ghost" size="sm" aria-pressed={highlighted} onClick={() => onShowEvidence(fact)}>
                  {t("docAi.showOnPage")}
                </Button>
              ) : null}
            </p>
          ) : null}
          <div className="mt-2.5 flex flex-wrap items-center gap-2">
            {stateChip}
            {fact.validation_status === "needs_review" ? (
              <ProvenanceChip kind="needsReview" label={t("ai.needsReview")} />
            ) : null}
            {fact.medical_record_id ? <Badge tone="info">{t("ai.addedToRecord")}</Badge> : null}
          </div>
        </div>

        <div className="flex w-full flex-wrap gap-1.5 sm:w-auto sm:justify-end">
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
                <CheckCircle size={15} weight="bold" aria-hidden />
                {t("ai.confirm")}
              </Button>
              <Button variant="ghost" size="sm" disabled={busy} onClick={() => setEditing(true)}>
                <PencilSimple size={15} aria-hidden />
                {t("ai.edit")}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="text-danger hover:bg-danger-soft"
                disabled={busy || rejected}
                onClick={() => onReview(fact.id, { action: "reject" })}
              >
                <Prohibit size={15} aria-hidden />
                {t("ai.reject")}
              </Button>
            </>
          )}
        </div>
      </div>
    </li>
  );
}
