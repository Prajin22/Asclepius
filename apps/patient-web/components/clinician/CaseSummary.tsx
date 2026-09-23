"use client";

import { errorMessage, useI18n } from "@carebridge/i18n";
import type {
  CaseSummary as CaseSummaryDTO,
  CaseSummaryItem,
  CaseSummarySource,
  SummarySectionKind,
} from "@carebridge/shared-types";
import { Alert, Button, Card, CardHeader, ProvenanceChip, Spinner, cn } from "@carebridge/ui";
import { ArrowRight, CaretDown, CaretUp } from "@phosphor-icons/react/dist/ssr";
import { useState } from "react";
import { languageLabel } from "@/lib/format";

/** One or many. The catalogue keeps both forms; `t` has no plural rules. */
function plural(t: (k: string, v?: Record<string, string | number>) => string, key: string, count: number) {
  return count === 1 ? t(`${key}One`) : t(key, { count });
}

/**
 * The Phase 4 case summary, in the doctor's case view.
 *
 * It is an organising layer over evidence the doctor can already read, and the
 * interface has to keep saying so. Three rules shape everything here:
 *
 * 1. **It must never look like a doctor's assessment.** Machine output wears the
 *    drawn crease — dashed edge, quiet ground, never ink, never vermilion. The
 *    doctor's own assessment keeps its inked identity further down the page.
 * 2. **Every statement leads back to a source.** One interaction opens the
 *    patient's own words, the confirmed item, the document page or the
 *    colleague's note that a line came from.
 * 3. **What is missing is said, not hidden.** Pending items, dropped items and
 *    staleness are all stated plainly, because a thinned summary that reads as a
 *    complete one is worse than no summary.
 */
export function CaseSummary({
  summary,
  loading,
  error,
  onGenerate,
  generating,
}: {
  summary: CaseSummaryDTO | undefined;
  loading: boolean;
  error: unknown;
  onGenerate: () => void;
  generating: boolean;
}) {
  const { t } = useI18n();

  return (
    <Card aria-labelledby="summary-heading">
      <CardHeader
        id="summary-heading"
        title={t("summary.title")}
        description={t("summary.subtitle")}
        // Marked with the product's machine styling, but labelled for what
        // this panel actually is. The shared default reads "AI extracted",
        // which describes Phase 2's operation, not this one — nothing here is
        // extracted, it is organised. Short, so it does not wrap on a phone.
        action={<ProvenanceChip kind="machine" label={t("summary.chip")} />}
      />

      {loading && !summary ? (
        <p className="text-small text-muted">{t("state.loading")}</p>
      ) : error && !summary ? (
        <Alert tone="error">{errorMessage(t, error)}</Alert>
      ) : (
        <Body summary={summary} onGenerate={onGenerate} generating={generating} error={error} />
      )}
    </Card>
  );
}

function Body({
  summary,
  onGenerate,
  generating,
  error,
}: {
  summary: CaseSummaryDTO | undefined;
  onGenerate: () => void;
  generating: boolean;
  error: unknown;
}) {
  const { t, formatDateTime } = useI18n();
  if (!summary) return null;

  const noneLeft = summary.generations_remaining === 0;
  const status = generating ? "generating" : summary.status;

  if (status === "generating") {
    return (
      <div className="flex flex-col gap-2" aria-live="polite" aria-busy="true">
        <p className="flex items-center gap-2 font-medium text-ink">
          <Spinner />
          {t("summary.generating")}
        </p>
        {/* Honest about what is happening: grouping, not analysis. */}
        <p className="text-small text-muted">{t("summary.generatingHint")}</p>
      </div>
    );
  }

  if (status === "not_generated") {
    return (
      <div className="flex flex-col gap-3">
        <p className="text-ink">{t("summary.notGenerated")}</p>
        <p className="text-small text-muted">{t("summary.notGeneratedHint")}</p>
        {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
        <GenerateButton onGenerate={onGenerate} disabled={noneLeft} remaining={summary.generations_remaining} />
      </div>
    );
  }

  if (status === "failed") {
    return (
      <div className="flex flex-col gap-3">
        <Alert tone="error">
          <span className="font-semibold">{t("summary.failed")}</span>
          {/* The case itself is untouched; say so, because that is what the
              doctor actually needs to know next. */}
          <span className="mt-0.5 block font-normal">{t("summary.failedHint")}</span>
        </Alert>
        {error ? <p className="text-small text-danger">{errorMessage(t, error)}</p> : null}
        <GenerateButton
          onGenerate={onGenerate}
          disabled={noneLeft}
          remaining={summary.generations_remaining}
          label={t("summary.retry")}
        />
      </div>
    );
  }

  const payload = summary.summary;
  if (!payload) return null;
  const isEmpty = payload.sections.length === 0 && payload.unresolved_notes.length === 0;

  return (
    <div className="flex flex-col gap-4">
      {summary.is_stale ? (
        <Alert tone="warning">
          <span className="font-semibold">{t("summary.stale")}</span>
          <span className="mt-0.5 block font-normal">{t("summary.staleHint")}</span>
        </Alert>
      ) : null}

      {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}

      {isEmpty ? (
        <p className="text-small text-muted">{t("summary.empty")}</p>
      ) : (
        <div className="flex flex-col gap-5">
          {payload.sections.map((section) => (
            <Section key={section.kind} kind={section.kind} items={section.items} />
          ))}

          {payload.unresolved_notes.length > 0 ? (
            <section aria-labelledby="summary-unresolved">
              <h3 id="summary-unresolved" className="text-label uppercase text-subtle">
                {t("summary.unresolvedTitle")}
              </h3>
              <ul className="mt-1.5 flex list-disc flex-col gap-1 pl-5 text-small text-muted">
                {payload.unresolved_notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      )}

      <Caveats summary={summary} />

      <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3">
        <p className="text-caption text-subtle">
          {summary.generated_at ? t("summary.generatedOn", { date: formatDateTime(summary.generated_at) }) : ""}
          {summary.provider ? (
            <span className="mt-0.5 block">
              {t(summary.is_external_provider ? "summary.generatedByExternal" : "summary.generatedBy", {
                provider: summary.provider,
                model: summary.model ?? "",
              })}
            </span>
          ) : null}
        </p>
        <GenerateButton
          onGenerate={onGenerate}
          disabled={noneLeft}
          remaining={summary.generations_remaining}
          label={summary.is_stale ? t("summary.refresh") : t("summary.regenerate")}
          variant={summary.is_stale ? "secondary" : "ghost"}
        />
      </footer>
    </div>
  );
}

function GenerateButton({
  onGenerate,
  disabled,
  remaining,
  label,
  variant = "secondary",
}: {
  onGenerate: () => void;
  disabled: boolean;
  remaining: number | null;
  label?: string;
  variant?: "secondary" | "ghost";
}) {
  const { t } = useI18n();
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button variant={variant} size="sm" onClick={onGenerate} disabled={disabled}>
        {label ?? t("summary.generate")}
      </Button>
      {/* The budget is a real constraint, so it is stated before it is hit. */}
      {remaining === 0 ? (
        <span className="text-small text-warning">{t("summary.generationsNone")}</span>
      ) : remaining != null ? (
        <span className="text-caption text-subtle">{plural(t, "summary.generationsLeft", remaining)}</span>
      ) : null}
    </div>
  );
}

/** What the summary does not contain, said plainly rather than left to be noticed. */
function Caveats({ summary }: { summary: CaseSummaryDTO }) {
  const { t } = useI18n();
  const payload = summary.summary;
  const pending = payload?.pending_fact_count ?? 0;
  const dropped = summary.dropped_item_count;
  const truncated = payload?.truncated ?? [];
  if (!pending && !dropped && truncated.length === 0) return null;

  return (
    <div className="flex flex-col gap-2 rounded-md border border-line bg-sunken px-3.5 py-3">
      {pending > 0 ? (
        <p className="text-small text-ink">
          <span className="font-semibold">{plural(t, "summary.pending", pending)}</span>{" "}
          <span className="text-muted">{t("summary.pendingHint")}</span>
        </p>
      ) : null}
      {dropped > 0 ? (
        <p className="text-small text-ink">
          <span className="font-semibold">{plural(t, "summary.droppedItems", dropped)}</span>{" "}
          <span className="text-muted">{t("summary.droppedHint")}</span>
        </p>
      ) : null}
      {truncated.length > 0 ? (
        <p className="text-small text-muted">{t("summary.truncated", { kinds: truncated.join(", ") })}</p>
      ) : null}
    </div>
  );
}

function Section({ kind, items }: { kind: SummarySectionKind; items: CaseSummaryItem[] }) {
  const { t } = useI18n();
  const headingId = `summary-section-${kind}`;
  return (
    <section aria-labelledby={headingId}>
      <h3 id={headingId} className="text-label uppercase text-subtle">
        {t(`summary.sectionHeading.${kind}`)}
      </h3>
      <ul className="mt-2 flex flex-col gap-2">
        {items.map((item, index) => (
          <Item key={`${kind}-${index}`} item={item} index={index} sectionKind={kind} />
        ))}
      </ul>
    </section>
  );
}

/** Attribution that is never allowed to be silent. */
function SubjectChip({ item }: { item: CaseSummaryItem }) {
  const { t } = useI18n();
  if (item.subject === null || item.subject === "self") return null;
  const label =
    item.subject === "family"
      ? t("summary.attributedFamily")
      : item.subject === "other"
        ? t("summary.attributedOther")
        : t("summary.attributedUnknown");
  return <ProvenanceChip kind="needsReview" label={label} />;
}

function Item({
  item,
  index,
  sectionKind,
}: {
  item: CaseSummaryItem;
  index: number;
  sectionKind: SummarySectionKind;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const panelId = `summary-sources-${sectionKind}-${index}`;
  const isFamily = item.subject === "family" || item.subject === "other" || item.subject === "unknown";

  return (
    <li
      className={cn(
        // Dashed: machine-organised. It must not read as an inked, authored line.
        "rounded-md border border-dashed bg-ai-soft/40 px-3.5 py-3",
        isFamily ? "border-mark-ink/50" : "border-ai-line",
        item.is_contradiction && "border-warning/60 bg-warning-soft/40",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="min-w-0 font-medium text-ink">
          {/* A relative's information never stands alone as a bare condition. */}
          {isFamily ? (
            <span className="mr-1.5 text-mark-ink">
              {item.subject_evidence ? `${item.subject_evidence} —` : `${t("summary.attributedFamily")} —`}
            </span>
          ) : null}
          {item.statement}
        </p>
        <span className="flex flex-wrap items-center gap-1.5">
          <SubjectChip item={item} />
          <OriginChip item={item} />
        </span>
      </div>

      {item.is_contradiction ? (
        <p className="mt-1.5 text-small text-warning">
          <span className="font-semibold">{t("summary.differs")}.</span> {t("summary.differsHint")}
        </p>
      ) : null}

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <CaretUp size={14} aria-hidden /> : <CaretDown size={14} aria-hidden />}
          {open ? t("summary.hideSource") : t("summary.viewSource")}
        </Button>
        <span className="text-caption text-subtle">{plural(t, "summary.sourceCount", item.sources.length)}</span>
      </div>

      {/* Always rendered so assistive technology can reach it through
          aria-controls; hidden rather than unmounted. */}
      <ul id={panelId} hidden={!open} className="mt-2 flex flex-col gap-2">
        {item.sources.map((source) => (
          <Source key={source.ref} source={source} />
        ))}
      </ul>
    </li>
  );
}

function OriginChip({ item }: { item: CaseSummaryItem }) {
  const { t } = useI18n();
  if (item.origin === "doctor_authored") {
    // Named, so a colleague's words are never mistaken for the machine's.
    const name = item.sources.find((s) => s.doctor_name)?.doctor_name;
    return <ProvenanceChip kind="doctor" label={name ? t("summary.authoredBy", { name }) : t("source.doctor")} />;
  }
  if (item.origin === "patient_confirmed") {
    return <ProvenanceChip kind="confirmed" label={t("ai.confirmedByPatient")} />;
  }
  return <ProvenanceChip kind="original" label={t("summary.patientReported")} />;
}

const SOURCE_LABEL: Record<CaseSummarySource["kind"], string> = {
  patient_statement: "summary.fromPatientStatement",
  current_problem: "summary.fromPatientStatement",
  health_record: "summary.fromHealthRecord",
  fact: "summary.fromConfirmedFact",
  document: "summary.fromDocument",
  prior_consultation: "summary.fromPriorConsultation",
  prior_prescription: "summary.fromPriorPrescription",
};

/**
 * One resolved source. Human-readable throughout: identifiers stay out of the
 * interface, and what a doctor sees is the patient's own words, the page a
 * value was read from, or the colleague who wrote a note.
 */
function Source({ source }: { source: CaseSummarySource }) {
  const { t, formatDate } = useI18n();
  const quote = source.original_text || source.quote;

  return (
    <li className="rounded-md border border-line bg-surface px-3 py-2.5">
      <div className="flex flex-wrap items-center gap-2 text-caption text-muted">
        <span className="font-semibold uppercase tracking-wide text-subtle">{t(SOURCE_LABEL[source.kind])}</span>
        {source.doctor_name ? <span>· {t("summary.authoredBy", { name: source.doctor_name })}</span> : null}
        {source.page_number != null ? <span>· {t("summary.onPage", { page: source.page_number })}</span> : null}
        {source.language ? <span>· {languageLabel(source.language)}</span> : null}
        {source.occurred_at ? <span>· {formatDate(source.occurred_at)}</span> : null}
      </div>

      {quote ? (
        <blockquote
          lang={source.language ?? undefined}
          // Vermilion paper: the patient's own material, unaltered.
          className="mt-1.5 whitespace-pre-line rounded-sm bg-paper px-2 py-1.5 text-body text-paper-ink"
        >
          {quote}
        </blockquote>
      ) : null}

      <p className="mt-1.5 flex flex-wrap items-center gap-1.5 text-caption text-subtle">
        <ArrowRight size={11} aria-hidden />
        {source.authorization_basis === "own_prior_consultation"
          ? t("summary.ownPriorBasis")
          : t("summary.grantedByPatient")}
      </p>
    </li>
  );
}
