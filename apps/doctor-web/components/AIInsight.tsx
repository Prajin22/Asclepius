"use client";

import { useI18n } from "@carebridge/i18n";
import { languageInfo, type AIFactSummary, type AIRecordInsight } from "@carebridge/shared-types";
import { Badge, Button, cn } from "@carebridge/ui";
import { useState } from "react";

const REVIEW_TONE = {
  confirmed: "success",
  edited: "success",
  pending: "warning",
  rejected: "danger",
} as const;

/**
 * Machine interpretation shown *beside* the patient's original text, never
 * instead of it. Collapsed by default so the original stays the first thing the
 * clinician reads. When opened, all three layers sit side by side: the
 * patient's words, the English version, and the structured items — with
 * attribution, evidence, the patient's confirmation, and a meaning check.
 */
export function AIInsight({ insight }: { insight: AIRecordInsight }) {
  const { t, formatDateTime } = useI18n();
  const [open, setOpen] = useState(false);

  if (insight.status === "not_processed") return null;

  const own = insight.facts.filter((f) => f.subject === "self");
  const others = insight.facts.filter((f) => f.subject !== "self");
  const check = insight.normalization_check;

  return (
    <div className="mt-3 rounded-lg border border-dashed border-ai/40 bg-ai-soft/30">
      <div className="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="ai">{t("ai.title")}</Badge>
          <span className="text-sm text-muted">{t("ai.machineGenerated")}</span>
          {check?.status === "review" ? <Badge tone="warning">{t("ai.view.checkReview")}</Badge> : null}
          {others.length > 0 ? <Badge tone="warning">{t("ai.view.subject.family")}</Badge> : null}
        </div>
        <Button variant="ghost" size="sm" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
          {open ? t("ai.hide") : t("ai.show")}
        </Button>
      </div>

      {open ? (
        <div className="flex flex-col gap-4 border-t border-ai/30 px-3.5 py-3">
          <p className="text-sm text-muted">{t("ai.subtitle")}</p>

          {insight.status === "unavailable" ? (
            <p className="text-sm font-medium text-warning">{t("ai.unavailable")}</p>
          ) : (
            <>
              <div className="grid gap-3 lg:grid-cols-2">
                <section>
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">{t("ai.view.original")}</h4>
                  <p
                    lang={insight.detected_language ?? undefined}
                    className="mt-1 whitespace-pre-line rounded-md bg-surface px-3 py-2"
                  >
                    {insight.original_text}
                  </p>
                  {insight.detected_language ? (
                    <p className="mt-1 text-sm text-muted">
                      {t("ai.detectedLanguage", {
                        language: languageInfo(insight.detected_language)?.englishName ?? insight.detected_language,
                      })}
                    </p>
                  ) : null}
                </section>
                <section>
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">
                    {t("ai.view.normalized")}
                  </h4>
                  <p className="mt-1 whitespace-pre-line rounded-md border border-ai/30 bg-surface px-3 py-2">
                    {insight.normalized_english}
                  </p>
                  {insight.unparsed.length > 0 ? (
                    <p className="mt-1 text-sm text-muted">
                      {t("ai.unparsed")}: {insight.unparsed.join(" · ")}
                    </p>
                  ) : null}
                </section>
              </div>

              {check ? (
                check.status === "ok" ? (
                  <p className="text-sm text-success">{t("ai.view.checkOk")}</p>
                ) : (
                  <div className="rounded-md border border-warning/40 bg-warning-soft px-3 py-2 text-sm text-warning">
                    <p className="font-semibold">{t("ai.view.checkReview")}</p>
                    {check.added_terms.length > 0 ? (
                      <p>
                        {t("ai.view.checkAdded")}: {check.added_terms.join(", ")}
                      </p>
                    ) : null}
                    {check.dropped_facts.length > 0 ? (
                      <p>
                        {t("ai.view.checkDropped")}: {check.dropped_facts.join(", ")}
                      </p>
                    ) : null}
                    {check.notes.includes("attribution_lost") ? <p>{t("ai.view.attributionLost")}</p> : null}
                  </div>
                )
              ) : null}

              <section>
                <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">{t("ai.view.facts")}</h4>
                {insight.facts.length === 0 ? (
                  <p className="mt-1 text-sm text-muted">{t("ai.none")}</p>
                ) : (
                  <>
                    <FactList facts={own} />
                    {others.length > 0 ? (
                      <div className="mt-3">
                        <p className="text-sm font-semibold text-warning">{t("ai.view.familyNote")}</p>
                        <FactList facts={others} />
                      </div>
                    ) : null}
                  </>
                )}
              </section>
            </>
          )}

          <p className="text-xs text-subtle">
            {t("ai.provenance", {
              provider: insight.provider ?? "",
              model: insight.model ?? "",
              date: insight.generated_at ? formatDateTime(insight.generated_at) : "",
            })}
          </p>
        </div>
      ) : null}
    </div>
  );
}

export function FactList({
  facts,
  active = null,
  onShowEvidence,
}: {
  facts: AIFactSummary[];
  /** Documents: the item whose evidence is outlined on the page image. */
  active?: AIFactSummary | null;
  onShowEvidence?: (fact: AIFactSummary) => void;
}) {
  const { t } = useI18n();
  if (facts.length === 0) return null;
  return (
    <ul className="mt-2 flex flex-col gap-2">
      {facts.map((fact, index) => (
        <li
          key={`${fact.category}-${fact.subject}-${index}`}
          className={cn(
            "rounded-md border bg-surface px-3 py-2",
            fact.subject === "self" ? "border-line" : "border-warning/40",
            fact === active && "ring-2 ring-ai",
          )}
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span>
              <span className="text-xs font-semibold uppercase tracking-wide text-muted">
                {t(`ai.category.${fact.category}`)}:{" "}
              </span>
              <span className="font-semibold">{fact.value}</span>
            </span>
            <span className="flex flex-wrap items-center gap-1.5">
              <Badge tone={fact.subject === "self" ? "neutral" : "warning"}>
                {t(`ai.view.subject.${fact.subject}`)}
              </Badge>
              {fact.validation_status === "needs_review" ? <Badge tone="warning">{t("ai.needsReview")}</Badge> : null}
              <Badge tone={REVIEW_TONE[fact.review_state]}>
                {fact.review_state === "confirmed"
                  ? t("ai.confirmedByPatient")
                  : fact.review_state === "edited"
                    ? t("ai.editedByPatient")
                    : t("ai.notConfirmed")}
              </Badge>
            </span>
          </div>
          <p className="mt-1 text-sm text-muted">
            <span className="font-medium">{t("ai.evidence")}: </span>
            <q>{fact.evidence_quote}</q>
          </p>
          {fact.subject_evidence ? (
            <p className="text-sm text-muted">{t("ai.view.attributedTo", { cue: fact.subject_evidence })}</p>
          ) : null}
          {fact.evidence_page_number != null ? (
            <p className="mt-0.5 flex flex-wrap items-center gap-2 text-sm text-muted">
              <span>{t("docAi.onPage", { page: fact.evidence_page_number })}</span>
              {onShowEvidence && fact.evidence_bbox ? (
                <Button variant="ghost" size="sm" aria-pressed={fact === active} onClick={() => onShowEvidence(fact)}>
                  {t("docAi.showOnPage")}
                </Button>
              ) : null}
            </p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
