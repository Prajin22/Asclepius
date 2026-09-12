"use client";

import { usePolling, useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import type { DoctorQueueItem } from "@carebridge/shared-types";
import {
  Avatar,
  ErrorState,
  PageHeader,
  SegmentedTabs,
  SkeletonCard,
  StatusBadge,
  cn,
} from "@carebridge/ui";
import { ArrowRight } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useState } from "react";
import { patientMeta } from "@/lib/format";

type Group = "incoming" | "active" | "completed";

function CaseRow({ item, dateLabel }: { item: DoctorQueueItem; dateLabel: string }) {
  const { t } = useI18n();
  return (
    <li>
      <Link
        href={`/cases/${item.id}`}
        className="group flex gap-3 border-b border-line px-4 py-3.5 transition-colors duration-150 last:border-b-0 hover:bg-sunken"
        aria-label={`${t("dashboard.openCase")}: ${item.patient.display_name}`}
      >
        <Avatar name={item.patient.display_name} />
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-semibold text-ink">{item.patient.display_name}</span>
            <StatusBadge status={item.status} />
          </span>
          <span className="block text-small text-muted">{patientMeta(item.patient, t)}</span>
          {item.current_problem_excerpt ? (
            <span className="mt-1.5 line-clamp-2 block border-l-[3px] border-l-paper-line bg-paper px-3 py-1.5 text-small text-paper-ink">
              {item.current_problem_excerpt}
            </span>
          ) : (
            <span className="mt-1.5 block text-small italic text-subtle">{t("dashboard.noProblemShared")}</span>
          )}
          <span className="mt-1.5 block text-caption text-subtle">{dateLabel}</span>
        </span>
        <ArrowRight
          size={18}
          aria-hidden
          className="mt-1 shrink-0 self-start text-subtle transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-brand"
        />
      </Link>
    </li>
  );
}

function Queue({ items, empty, dateOf }: { items: DoctorQueueItem[]; empty: string; dateOf: (i: DoctorQueueItem) => string }) {
  if (items.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-line-strong bg-sunken/60 px-4 py-8 text-center text-muted">
        {empty}
      </p>
    );
  }
  return (
    <ul className="overflow-hidden rounded-xl border border-line bg-surface">
      {items.map((item) => (
        <CaseRow key={item.id} item={item} dateLabel={dateOf(item)} />
      ))}
    </ul>
  );
}

export default function DoctorDashboard() {
  const { t, formatDateTime } = useI18n();
  const q = useQuery((a) => a.doctor.queue());
  usePolling(q.reload, 10000, true);
  const [group, setGroup] = useState<Group>("incoming");

  if (q.error && !q.data) return <ErrorState error={q.error} onRetry={q.reload} />;
  if (!q.data) return <SkeletonCard />;

  const incoming = q.data.filter((i) => i.status === "requested");
  const active = q.data.filter((i) => i.status === "accepted" || i.status === "active");
  const completed = q.data.filter((i) => i.status === "completed");

  const groups = {
    incoming: {
      items: incoming,
      empty: t("dashboard.emptyIncoming"),
      dateOf: (i: DoctorQueueItem) => t("dashboard.requested", { date: formatDateTime(i.created_at) }),
    },
    active: {
      items: active,
      empty: t("dashboard.emptyActive"),
      dateOf: (i: DoctorQueueItem) => t("dashboard.started", { date: formatDateTime(i.started_at ?? i.created_at) }),
    },
    completed: {
      items: completed,
      empty: t("dashboard.emptyCompleted"),
      dateOf: (i: DoctorQueueItem) => t("dashboard.completedOn", { date: formatDateTime(i.completed_at ?? i.created_at) }),
    },
  } as const;

  return (
    <>
      <PageHeader title={t("dashboard.title")} description={t("dashboard.subtitle")} />

      {/* One queue at a time on a phone; all three side by side on a wide screen. */}
      <div className="lg:hidden">
        <SegmentedTabs
          label={t("dashboard.title")}
          value={group}
          onChange={setGroup}
          items={[
            { value: "incoming", label: t("dashboard.incoming"), badge: incoming.length },
            { value: "active", label: t("dashboard.active"), badge: active.length },
            { value: "completed", label: t("dashboard.completed"), badge: completed.length },
          ]}
        />
        <div className="mt-4">
          <Queue {...groups[group]} />
        </div>
      </div>

      <div className="hidden gap-5 lg:grid lg:grid-cols-3">
        {(["incoming", "active", "completed"] as const).map((key) => (
          <section key={key} aria-labelledby={`queue-${key}`} className="min-w-0">
            <h2
              id={`queue-${key}`}
              className={cn(
                "mb-3 flex items-center justify-between gap-2 text-subheading",
                key === "incoming" ? "text-ink" : "text-muted",
              )}
            >
              {t(`dashboard.${key === "completed" ? "completed" : key}`)}
              <span className="tabular rounded-full bg-sunken px-2 py-0.5 text-small font-semibold text-muted">
                {groups[key].items.length}
              </span>
            </h2>
            <Queue {...groups[key]} />
          </section>
        ))}
      </div>
    </>
  );
}
