"use client";

import { usePolling, useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import type { DoctorQueueItem } from "@carebridge/shared-types";
import { ErrorState, PageHeader, SegmentedTabs, SkeletonCard, cn } from "@carebridge/ui";
import { useState } from "react";
import { QueueList } from "@/components/clinician/CaseRow";

type Group = "incoming" | "active" | "completed";

export default function DoctorConsultations() {
  const { t, formatDateTime } = useI18n();
  const q = useQuery((a) => a.doctor.queue());
  usePolling(q.reload, 10000, true);
  // Until the doctor picks a group, show the first one that has anything in it:
  // landing on an empty "Incoming" while cases wait under another tab helps nobody.
  const [chosen, setChosen] = useState<Group | null>(null);

  if (q.error && !q.data) return <ErrorState error={q.error} onRetry={q.reload} />;
  if (!q.data) return <SkeletonCard />;

  const incoming = q.data.filter((i) => i.status === "requested");
  const active = q.data.filter((i) => i.status === "accepted" || i.status === "active");
  const completed = q.data.filter((i) => i.status === "completed");
  const group: Group = chosen ?? (incoming.length ? "incoming" : active.length ? "active" : "completed");

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
          onChange={setChosen}
          items={[
            { value: "incoming", label: t("dashboard.incoming"), badge: incoming.length },
            { value: "active", label: t("dashboard.active"), badge: active.length },
            { value: "completed", label: t("dashboard.completed"), badge: completed.length },
          ]}
        />
        <div className="mt-4">
          <QueueList {...groups[group]} />
        </div>
      </div>

      <div className="hidden gap-5 lg:grid lg:grid-cols-3">
        {(["incoming", "active", "completed"] as const).map((key) => (
          <section key={key} aria-labelledby={`queue-${key}`} className="min-w-0">
            <h2
              id={`queue-${key}`}
              className={cn(
                "mb-3 flex items-center justify-between gap-2 text-heading",
                key === "incoming" ? "text-ink" : "text-muted",
              )}
            >
              {t(`dashboard.${key}`)}
              <span className="tabular text-small font-normal text-muted">{groups[key].items.length}</span>
            </h2>
            <QueueList {...groups[key]} />
          </section>
        ))}
      </div>
    </>
  );
}
