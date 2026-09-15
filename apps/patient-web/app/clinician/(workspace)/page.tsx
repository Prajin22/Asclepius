"use client";

import { usePolling, useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import { ErrorState, Mark, PageHeader, SkeletonCard, buttonClasses } from "@carebridge/ui";
import Link from "next/link";
import { QueueList } from "@/components/clinician/CaseRow";
import { HOME_FOR_ROLE } from "@/lib/routes";

/**
 * The doctor's first screen answers one question: what is waiting for me.
 *
 * Requests to review come first, then consultations already under way. No
 * analytics, no ranking of patients, no triage: this is a work list, in the order
 * the work arrived.
 */
export default function DoctorHome() {
  const { t, formatDateTime } = useI18n();
  const q = useQuery((a) => a.doctor.queue());
  usePolling(q.reload, 10000, true);

  if (q.error && !q.data) return <ErrorState error={q.error} onRetry={q.reload} />;
  if (!q.data) return <SkeletonCard />;

  const incoming = q.data.filter((i) => i.status === "requested");
  const active = q.data.filter((i) => i.status === "accepted" || i.status === "active");

  return (
    <>
      <PageHeader
        title={t("home.title")}
        description={t("home.subtitle")}
        actions={
          <Link href={`${HOME_FOR_ROLE.doctor}/consultations`} className={buttonClasses("secondary", "md")}>
            {t("home.viewAll")}
          </Link>
        }
      />

      <div className="flex flex-col gap-8">
        <section aria-labelledby="incoming-heading">
          <div className="mb-3 flex items-center gap-2">
            {incoming.length > 0 ? <Mark /> : null}
            <h2 id="incoming-heading" className="text-heading text-ink">
              {t("dashboard.incoming")}
            </h2>
            <span className="tabular text-small text-muted">{incoming.length}</span>
          </div>
          <QueueList
            items={incoming}
            empty={t("dashboard.emptyIncoming")}
            emptyWhy={t("home.incomingWhy")}
            dateOf={(i) => t("dashboard.requested", { date: formatDateTime(i.created_at) })}
          />
        </section>

        <section aria-labelledby="active-heading">
          <div className="mb-3 flex items-center gap-2">
            <h2 id="active-heading" className="text-heading text-ink">
              {t("dashboard.active")}
            </h2>
            <span className="tabular text-small text-muted">{active.length}</span>
          </div>
          <QueueList
            items={active}
            empty={t("dashboard.emptyActive")}
            emptyWhy={t("home.activeWhy")}
            dateOf={(i) => t("dashboard.started", { date: formatDateTime(i.started_at ?? i.created_at) })}
          />
        </section>
      </div>
    </>
  );
}
