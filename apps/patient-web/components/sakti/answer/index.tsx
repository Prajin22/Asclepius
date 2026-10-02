"use client";

/**
 * The pieces a cited answer will be shown with (Phase 4). In Phase 3.5 they
 * render only their empty states on screen; the answer types in `./types`
 * define what they will receive. Two rules are built in, not left to callers:
 *
 *  - India and International are separate panels with their own name, icon
 *    and ruled edge. Nothing here can render one lane inside the other.
 *  - Legal words appear only as quotations, on the source ("parchment")
 *    material, with the authority, instrument, label, version, dates and
 *    checksum that identify them. A point without a citation is not rendered.
 */
import { useI18n, useT } from "@carebridge/i18n";
import { Badge, Button, cn, type Tone } from "@carebridge/ui";
import {
  CalendarBlank,
  CheckCircle,
  CircleDashed,
  Info,
  Lifebuoy,
  ListChecks,
  Quotes,
  WarningCircle,
} from "@phosphor-icons/react/dist/ssr";
import type { Icon } from "@phosphor-icons/react";
import type { ReactNode } from "react";
import { LaneMark, laneRule } from "../ui";
import type { AnswerPoint as AnswerPointData, Confidence, Jurisdiction, LaneAnswer, QuotedProvision } from "./types";

const CONFIDENCE: Record<Confidence, { tone: Tone; icon: Icon }> = {
  supported: { tone: "success", icon: CheckCircle },
  partial: { tone: "warning", icon: WarningCircle },
  insufficient: { tone: "neutral", icon: CircleDashed },
};

/** How far the cited text supports an answer — in words, with an icon. Never a percentage. */
export function ConfidenceBadge({ level }: { level: Confidence }) {
  const t = useT();
  const { tone, icon: Glyph } = CONFIDENCE[level];
  return (
    <Badge tone={tone}>
      <Glyph size={13} weight="bold" aria-hidden />
      {t(`answer.confidence.${level}`)}
    </Badge>
  );
}

/** "As of" — the date the law is read at. */
export function AsOfDate({ date, className }: { date: string; className?: string }) {
  const { t, formatDate } = useI18n();
  return (
    <p className={cn("inline-flex items-center gap-1.5 text-small text-muted", className)}>
      <CalendarBlank size={15} aria-hidden />
      {t("answer.asOf", { date: formatDate(date) })}
    </p>
  );
}

/**
 * One quotation of approved official text, as an evidence object: who
 * published it, which instrument and label, the exact words, and the version,
 * dates, status and checksum that let anyone check it against the corpus.
 */
export function SourceCitation({ quote, number }: { quote: QuotedProvision; number: number }) {
  const { t, formatDate } = useI18n();
  const s = quote.source;
  const validity =
    s.validFrom || s.validTo
      ? t("answer.citation.validRange", {
          from: s.validFrom ? formatDate(s.validFrom) : t("answer.citation.open"),
          to: s.validTo ? formatDate(s.validTo) : t("answer.citation.open"),
        })
      : t("answer.citation.notRecorded");
  return (
    <figure
      id={`citation-${s.provisionVersionId}-${number}`}
      className="overflow-hidden rounded-md border border-source-line bg-source text-source-ink"
    >
      <header className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-source-line/70 px-4 py-2.5">
        <span className="grid size-6 shrink-0 place-items-center rounded-sm bg-source-ink text-caption font-bold text-source">
          {number}
        </span>
        <LaneMark lane={s.lane} size="sm" />
        <span className="text-small font-semibold">{t(`corpus.authority.${s.authority}`)}</span>
        <span className="min-w-0 basis-full text-small sm:basis-auto">
          <cite className="not-italic">{s.instrumentTitle}</cite>
          <span aria-hidden> · </span>
          <span className="font-semibold">{s.locator}</span>
        </span>
      </header>
      <blockquote className="relative px-4 py-3.5 pl-10">
        <Quotes size={18} weight="fill" aria-hidden className="absolute left-4 top-4 text-source-line" />
        <p className="whitespace-pre-line leading-relaxed">{quote.text}</p>
      </blockquote>
      {quote.ocrDerived ? (
        <p className="flex items-start gap-2 border-t border-source-line/70 px-4 py-2 text-small">
          <Info size={15} aria-hidden className="mt-0.5 shrink-0" />
          {t("answer.citation.ocr")}
        </p>
      ) : null}
      <figcaption className="border-t border-source-line/70 px-4 py-2.5">
        <dl className="grid gap-x-5 gap-y-1 text-caption sm:grid-cols-2">
          <Meta label={t("answer.citation.version")}>{s.versionNumber}</Meta>
          <Meta label={t("answer.citation.validity")}>{validity}</Meta>
          <Meta label={t("answer.citation.status")}>{s.status ? t(`corpus.status.${s.status}`) : t("answer.citation.noStatus")}</Meta>
          <Meta label={t("answer.citation.retrieved")}>{formatDate(s.retrievedOn)}</Meta>
          <Meta label={t("answer.citation.source")}>{s.sourceTitle}</Meta>
          <Meta label={t("answer.citation.checksum")}>
            <code className="break-all">{s.textSha256.slice(0, 16)}…</code>
          </Meta>
        </dl>
      </figcaption>
    </figure>
  );
}

function Meta({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 gap-1.5">
      <dt className="shrink-0 font-semibold">{label}</dt>
      <dd className="min-w-0">{children}</dd>
    </div>
  );
}

/** One point of an answer: a statement about the quoted text, and the quotations themselves. */
export function AnswerPoint({ point, startAt }: { point: AnswerPointData; startAt: number }) {
  const t = useT();
  if (point.citations.length === 0) return null; // An uncited statement is never shown.
  return (
    <li className="flex flex-col gap-3">
      <div className="flex items-start gap-2.5">
        <span className="mt-0.5 shrink-0">
          <Badge tone={point.kind === "requirement" ? "brand" : "neutral"}>
            {point.kind === "requirement" ? <ListChecks size={13} weight="bold" aria-hidden /> : <Info size={13} weight="bold" aria-hidden />}
            {t(`answer.point.${point.kind}`)}
          </Badge>
        </span>
        <p className="min-w-0 text-ink">
          {point.statement}{" "}
          {point.citations.map((c, i) => (
            <a
              key={i}
              href={`#citation-${c.source.provisionVersionId}-${startAt + i}`}
              className="ml-0.5 rounded-sm bg-source px-1 text-caption font-bold text-source-ink ring-1 ring-source-line hover:underline"
            >
              <span className="sr-only">{t("answer.point.citation")} </span>
              {startAt + i}
            </a>
          ))}
        </p>
      </div>
      <div className="flex flex-col gap-2.5 pl-0 sm:pl-6">
        {point.citations.map((c, i) => (
          <SourceCitation key={i} quote={c} number={startAt + i} />
        ))}
      </div>
    </li>
  );
}

/** What the approved sources do not cover. Said plainly, never filled in. */
export function NotCovered({ items }: { items: string[] }) {
  const t = useT();
  if (items.length === 0) return null;
  return (
    <section className="rounded-md border border-dashed border-line-strong bg-sunken/60 p-4">
      <h3 className="flex items-center gap-2 text-small font-semibold text-ink">
        <CircleDashed size={16} weight="bold" aria-hidden />
        {t("answer.notCovered.title")}
      </h3>
      <ul className="mt-2 flex list-disc flex-col gap-1 pl-5 text-small text-muted">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

/** When the sources are not enough: a person can look. Escalation itself opens in a later release. */
export function EscalationSuggestion({ reason, available = false }: { reason?: string; available?: boolean }) {
  const t = useT();
  return (
    <section className="flex flex-col gap-3 rounded-md border border-line bg-surface p-4">
      <div className="flex items-start gap-3">
        <Lifebuoy size={22} aria-hidden className="mt-0.5 shrink-0 text-brand" />
        <div>
          <h3 className="font-semibold text-ink">{t("answer.escalate.title")}</h3>
          <p className="text-small text-muted">{reason ?? t("answer.escalate.body")}</p>
        </div>
      </div>
      <div className="flex flex-col items-start gap-1 sm:pl-9">
        <Button variant="secondary" size="sm" disabled={!available}>
          {t("answer.escalate.action")}
        </Button>
        {available ? null : <span className="text-caption text-subtle">{t("answer.escalate.later")}</span>}
      </div>
    </section>
  );
}

/**
 * One lane's answer, or the lane's empty state. The lane is named, iconed and
 * ruled at the edge; its scope says which sources it may ever draw on.
 */
export function AnswerPanel({ lane, answer, empty }: { lane: Jurisdiction; answer?: LaneAnswer | null; empty?: ReactNode }) {
  const t = useT();
  const headingId = `answer-${lane}`;
  let n = 1;
  return (
    <section aria-labelledby={headingId} className={cn("flex flex-col rounded-md border border-line bg-surface", laneRule(lane))}>
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
        <div className="min-w-0">
          <LaneMark lane={lane} size="sm" />
          <h2 id={headingId} className="mt-2 text-subheading text-ink">
            {t(`answer.lane.${lane}.title`)}
          </h2>
          <p className="mt-0.5 text-small text-muted">{t(`answer.lane.${lane}.scope`)}</p>
        </div>
        {answer ? <ConfidenceBadge level={answer.confidence} /> : null}
      </header>
      <div className="flex flex-1 flex-col gap-5 px-5 py-5">
        {answer ? (
          <>
            <AsOfDate date={answer.asOf} />
            {answer.points.length ? (
              <ol className="flex flex-col gap-6">
                {answer.points.map((p) => {
                  const start = n;
                  n += p.citations.length;
                  return <AnswerPoint key={p.id} point={p} startAt={start} />;
                })}
              </ol>
            ) : null}
            <NotCovered items={answer.notCovered} />
          </>
        ) : (
          empty
        )}
      </div>
    </section>
  );
}
