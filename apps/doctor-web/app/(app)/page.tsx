"use client";

import { usePolling, useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import type { DoctorQueueItem } from "@carebridge/shared-types";
import { ErrorState, LoadingState, PageHeader, StatusBadge, cn } from "@carebridge/ui";
import Link from "next/link";
import { patientMeta } from "@/lib/format";

function QueueColumn({
  title,
  items,
  empty,
  accent,
  dateOf,
}: {
  title: string;
  items: DoctorQueueItem[];
  empty: string;
  accent: string;
  dateOf: (i: DoctorQueueItem) => string;
}) {
  const { t } = useI18n();
  return (
    <section aria-label={title} className="flex min-w-0 flex-col rounded-xl border border-line bg-surface">
      <header className={cn("flex items-center justify-between gap-2 rounded-t-xl border-b border-line px-4 py-3", accent)}>
        <h2 className="font-semibold">{title}</h2>
        <span className="rounded-full bg-surface px-2.5 py-0.5 text-sm font-semibold tabular-nums">{items.length}</span>
      </header>
      {items.length === 0 ? (
        <p className="px-4 py-6 text-sm text-muted">{empty}</p>
      ) : (
        <ul className="flex flex-col divide-y divide-line">
          {items.map((i) => (
            <li key={i.id}>
              <Link href={`/cases/${i.id}`} className="block px-4 py-3.5 hover:bg-sunken" aria-label={`${t("dashboard.openCase")}: ${i.patient.display_name}`}>
                <div className="flex items-start justify-between gap-2">
                  <p className="font-semibold">{i.patient.display_name}</p>
                  <StatusBadge status={i.status} />
                </div>
                <p className="text-sm text-muted">{patientMeta(i.patient, t)}</p>
                {i.current_problem_excerpt ? (
                  <p className="mt-1.5 line-clamp-3 text-sm">{i.current_problem_excerpt}</p>
                ) : (
                  <p className="mt-1.5 text-sm italic text-subtle">{t("dashboard.noProblemShared")}</p>
                )}
                <p className="mt-1.5 text-xs text-muted">{dateOf(i)}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function DoctorDashboard() {
  const { t, formatDateTime } = useI18n();
  const q = useQuery((a) => a.doctor.queue());
  usePolling(q.reload, 10000, true);

  if (q.error && !q.data) return <ErrorState error={q.error} onRetry={q.reload} />;
  if (!q.data) return <LoadingState />;

  const incoming = q.data.filter((i) => i.status === "requested");
  const active = q.data.filter((i) => i.status === "accepted" || i.status === "active");
  const completed = q.data.filter((i) => i.status === "completed");

  return (
    <>
      <PageHeader title={t("dashboard.title")} description={t("dashboard.subtitle")} />
      <div className="grid gap-5 lg:grid-cols-3">
        <QueueColumn
          title={t("dashboard.incoming")}
          items={incoming}
          empty={t("dashboard.emptyIncoming")}
          accent="bg-warning-soft"
          dateOf={(i) => t("dashboard.requested", { date: formatDateTime(i.created_at) })}
        />
        <QueueColumn
          title={t("dashboard.active")}
          items={active}
          empty={t("dashboard.emptyActive")}
          accent="bg-success-soft"
          dateOf={(i) => t("dashboard.started", { date: formatDateTime(i.started_at ?? i.created_at) })}
        />
        <QueueColumn
          title={t("dashboard.completed")}
          items={completed}
          empty={t("dashboard.emptyCompleted")}
          accent="bg-sunken"
          dateOf={(i) => t("dashboard.completedOn", { date: formatDateTime(i.completed_at ?? i.created_at) })}
        />
      </div>
    </>
  );
}
