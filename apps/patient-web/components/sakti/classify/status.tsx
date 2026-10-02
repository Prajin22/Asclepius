"use client";

import { useI18n, useT } from "@carebridge/i18n";
import type { ClassificationStatus, ClassificationSummary } from "@carebridge/shared-types";
import { Badge, cn, type Tone } from "@carebridge/ui";
import {
  ArrowsClockwise,
  Clock,
  HourglassMedium,
  Question,
  SealCheck,
  XCircle,
} from "@phosphor-icons/react/dist/ssr";
import type { Icon } from "@phosphor-icons/react";
import Link from "next/link";

export const STATUS_TONE: Record<ClassificationStatus, Tone> = {
  incomplete: "info",
  requires_information: "warning",
  determined: "brand",
  user_confirmed: "success",
  user_rejected: "neutral",
  superseded: "neutral",
};

const STATUS_ICON: Record<ClassificationStatus, Icon> = {
  incomplete: HourglassMedium,
  requires_information: Question,
  determined: Clock,
  user_confirmed: SealCheck,
  user_rejected: XCircle,
  superseded: ArrowsClockwise,
};

/** A classification session's status: icon, word and tone together. */
export function SessionBadge({ status, className }: { status: ClassificationStatus; className?: string }) {
  const t = useT();
  const Glyph = STATUS_ICON[status];
  return (
    <Badge tone={STATUS_TONE[status]} className={className}>
      <Glyph size={13} weight="bold" aria-hidden />
      {t(`classifier.status.${status}`)}
    </Badge>
  );
}

/**
 * Every classification of one product, newest first, as a read-only timeline:
 * when it started, which classifier version it used, what it led to, whether
 * the user confirmed it, and whether it was a restart. Nothing here can be
 * changed; each entry opens the session as it stands.
 */
export function ClassificationTimeline({ history }: { history: ClassificationSummary[] }) {
  const { t, formatDateTime } = useI18n();
  if (history.length === 0) return <p className="text-muted">{t("classifier.timeline.empty")}</p>;
  return (
    <ol className="relative flex flex-col">
      {history.map((s, i) => {
        const Glyph = STATUS_ICON[s.status];
        const number = history.length - i;
        const last = i === history.length - 1;
        return (
          <li key={s.id} className="relative flex gap-4 pb-6 last:pb-0">
            {/* The rail joining one entry to the next. */}
            {last ? null : <span aria-hidden className="absolute left-[15px] top-9 bottom-1 w-px bg-line" />}
            <span
              aria-hidden
              className={cn(
                "relative z-[1] grid size-8 shrink-0 place-items-center rounded-full border bg-surface",
                s.status === "user_confirmed" ? "border-success/40 text-success" : "border-line-strong/60 text-muted",
              )}
            >
              <Glyph size={16} weight="bold" />
            </span>
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-small font-semibold text-muted">{t("classifier.timeline.session", { number })}</p>
                <SessionBadge status={s.status} />
              </div>
              <p className="mt-1 text-subheading text-ink">
                {s.category ? t(`classifier.category.${s.category}`) : t("classifier.timeline.noCategory")}
              </p>
              <dl className="mt-2 flex flex-col gap-1 text-small">
                <div className="flex flex-wrap gap-x-1.5">
                  <dt className="text-muted">{t("classifier.timeline.started")}</dt>
                  <dd className="text-ink">{formatDateTime(s.created_at)}</dd>
                </div>
                <div className="flex flex-wrap gap-x-1.5">
                  <dt className="text-muted">{t("classifier.timeline.version")}</dt>
                  <dd className="text-ink">{s.tree_version}</dd>
                </div>
                {s.decided_at ? (
                  <div className="flex flex-wrap gap-x-1.5">
                    <dt className="text-muted">
                      {t(
                        s.status === "user_rejected"
                          ? "classifier.timeline.rejected"
                          : s.status === "user_confirmed"
                            ? "classifier.timeline.confirmed"
                            : "classifier.timeline.decided",
                      )}
                    </dt>
                    <dd className="text-ink">{formatDateTime(s.decided_at)}</dd>
                  </div>
                ) : null}
              </dl>
              {s.restarted_from_id ? (
                <p className="mt-1.5 flex items-center gap-1.5 text-small text-muted">
                  <ArrowsClockwise size={14} aria-hidden />
                  {t("classifier.timeline.restart")}
                </p>
              ) : null}
              <Link
                href={`/classify/${s.id}`}
                className="mt-2 inline-flex min-h-11 items-center text-small font-semibold text-brand-strong hover:underline sm:min-h-0"
              >
                {t("classifier.timeline.open")}
                <span className="sr-only"> — {t("classifier.timeline.session", { number })}</span>
              </Link>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
