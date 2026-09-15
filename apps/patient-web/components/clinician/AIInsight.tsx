"use client";

import { useI18n } from "@carebridge/i18n";
import { languageInfo, type AIFactSummary, type AIRecordInsight } from "@carebridge/shared-types";
import { Button, ProvenanceBlock, ProvenanceChip, cn } from "@carebridge/ui";
import { CaretDown, CaretUp } from "@phosphor-icons/react/dist/ssr";
import { useState } from "react";

/**
 * Machine interpretation shown *beside* the patient's original text, never
 * instead of it. Collapsed by default so the original stays the first thing the
 * clinician reads. When opened, all three layers sit side by side: the patient's
 * words, the English version, and the structured items — with attribution,
 * evidence, the patient's confirmation, and a meaning check.
 */
export function AIInsight({ insight }: { insight: AIRecordInsight }) {
  const { t, formatDateTime } = useI18n();
  const [open, setOpen] = useState(false);

  if (insight.status === "not_processed") return null;

  const own = insight.facts.filter((f) => f.subject === "self");
  const others = insight.facts.filter((f) => f.subject !== "self");
  const check = insight.normalization_check;

  return (
    <div className="mt-3 rounded-md border border-dashed border-ai-line bg-ai-soft/60">
      <div className="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <ProvenanceChip kind="machine" label={t("ai.title")} />
          <span className="text-small text-muted">{t("ai.machineGenerated")}</span>
          {check?.status === "review" ? <ProvenanceChip kind="needsReview" label={t("ai.view.checkReview")} /> : null}
          {others.length > 0 ? <ProvenanceChip kind="needsReview" label={t("ai.view.subject.family")} /> : null}
        </div>
        <Button variant="ghost" size="sm" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
          {open ? <CaretUp size={15} aria-hidden /> : <CaretDown size={15} aria-hidden />}
          {open ? t("ai.hide") : t("ai.show")}
        </Button>
      </div>

      {open ? (
        <div className="flex flex-col gap-4 border-t border-ai-line/70 px-3.5 py-3.5">
          <p className="text-small text-muted">{t("ai.subtitle")}</p>

          {insight.status === "unavailable" ? (
            <p className="text-small font-medium text-warning">{t("ai.unavailable")}</p>
          ) : (
            <>
              <div className="grid gap-3 lg:grid-cols-2">
                <section>
                  <h4 className="text-label uppercase text-subtle">{t("ai.view.original")}</h4>
                  <ProvenanceBlock kind="original" className="mt-1.5">
                    {/* The language belongs on the text itself, for screen readers and font selection. */}
                    <p lang={insight.detected_language ?? undefined} className="whitespace-pre-line">
                      {insight.original_text}
                    </p>
                  </ProvenanceBlock>
                  {insight.detected_language ? (
                    <p className="mt-1 text-small text-muted">
                      {t("ai.detectedLanguage", {
                        language: languageInfo(insight.detected_language)?.englishName ?? insight.detected_language,
                      })}
                    </p>
                  ) : null}
                </section>
                <section>
                  <h4 className="text-label uppercase text-subtle">{t("ai.view.normalized")}</h4>
                  <ProvenanceBlock kind="machine" className="mt-1.5">
                    <p className="whitespace-pre-line">{insight.normalized_english}</p>
                    {insight.unparsed.length > 0 ? (
                      <p className="mt-1 text-small text-muted">
                        {t("ai.unparsed")}: {insight.unparsed.join(" · ")}
                      </p>
                    ) : null}
                  </ProvenanceBlock>
                </section>
              </div>

              {check ? (
                check.status === "ok" ? (
                  <p className="text-small text-success">{t("ai.view.checkOk")}</p>
                ) : (
                  <div className="rounded-md border border-warning/40 bg-warning-soft px-3 py-2 text-small text-warning">
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
                <h4 className="text-label uppercase text-subtle">{t("ai.view.facts")}</h4>
                {insight.facts.length === 0 ? (
                  <p className="mt-1 text-small text-muted">{t("ai.none")}</p>
                ) : (
                  <>
                    <FactList facts={own} />
                    {others.length > 0 ? (
                      <div className="mt-3">
                        <p className="text-small font-semibold text-warning">{t("ai.view.familyNote")}</p>
                        <FactList facts={others} />
                      </div>
                    ) : null}
                  </>
                )}
              </section>
            </>
          )}

          <p className="text-caption text-subtle">
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
            "rounded-md border bg-surface px-3 py-2.5",
            fact.subject === "self" ? "border-line" : "border-warning/50",
            fact === active && "ring-2 ring-mark",
          )}
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <span className="min-w-0">
              <span className="text-label uppercase text-subtle">{t(`ai.category.${fact.category}`)}</span>
              <span className="mt-0.5 block font-semibold text-ink">{fact.value}</span>
            </span>
            <span className="flex flex-wrap items-center gap-1.5">
              <ProvenanceChip
                kind={fact.subject === "self" ? "pending" : "needsReview"}
                label={t(`ai.view.subject.${fact.subject}`)}
              />
              {fact.validation_status === "needs_review" ? (
                <ProvenanceChip kind="needsReview" label={t("ai.needsReview")} />
              ) : null}
              <ProvenanceChip
                kind={
                  fact.review_state === "confirmed" || fact.review_state === "edited"
                    ? "confirmed"
                    : fact.review_state === "rejected"
                      ? "rejected"
                      : "pending"
                }
                label={
                  fact.review_state === "confirmed"
                    ? t("ai.confirmedByPatient")
                    : fact.review_state === "edited"
                      ? t("ai.editedByPatient")
                      : t("ai.notConfirmed")
                }
              />
            </span>
          </div>
          <p className="mt-1.5 text-small text-muted">
            <span className="font-medium">{t("ai.evidence")}: </span>
            <q className="rounded-sm bg-paper px-1 py-0.5 text-paper-ink">{fact.evidence_quote}</q>
          </p>
          {fact.subject_evidence ? (
            <p className="text-small text-muted">{t("ai.view.attributedTo", { cue: fact.subject_evidence })}</p>
          ) : null}
          {fact.evidence_page_number != null ? (
            <p className="mt-0.5 flex flex-wrap items-center gap-2 text-small text-muted">
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
