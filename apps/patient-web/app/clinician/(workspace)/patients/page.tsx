"use client";

import { useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import type { DoctorQueueItem } from "@carebridge/shared-types";
import { Avatar, EmptyState, ErrorState, PageHeader, SkeletonCard, StatusBadge } from "@carebridge/ui";
import { ArrowRight } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { patientMeta } from "@/lib/format";
import { HOME_FOR_ROLE } from "@/lib/routes";

interface PatientGroup {
  id: string;
  latest: DoctorQueueItem;
  items: DoctorQueueItem[];
}

/**
 * The same consultations, grouped by the person they are with.
 *
 * Derived in the browser from the queue the workspace already loads: a doctor
 * sees a patient only through consultations, so no new endpoint and no new data.
 */
function groupByPatient(items: DoctorQueueItem[]): PatientGroup[] {
  const byPatient = new Map<string, PatientGroup>();
  for (const item of items) {
    const group = byPatient.get(item.patient.id);
    if (group) group.items.push(item);
    else byPatient.set(item.patient.id, { id: item.patient.id, latest: item, items: [item] });
  }
  for (const group of byPatient.values()) {
    group.items.sort((a, b) => b.created_at.localeCompare(a.created_at));
    group.latest = group.items[0]!;
  }
  return [...byPatient.values()].sort((a, b) => b.latest.created_at.localeCompare(a.latest.created_at));
}

export default function DoctorPatients() {
  const { t, formatDate } = useI18n();
  const q = useQuery((a) => a.doctor.queue());

  if (q.error && !q.data) return <ErrorState error={q.error} onRetry={q.reload} />;
  if (!q.data) return <SkeletonCard />;

  const groups = groupByPatient(q.data);

  return (
    <>
      <PageHeader title={t("patients.title")} description={t("patients.subtitle")} />
      {groups.length === 0 ? (
        <EmptyState title={t("patients.empty")}>{t("patients.emptyWhy")}</EmptyState>
      ) : (
        <ul className="overflow-hidden rounded-md border border-line bg-surface">
          {groups.map((group) => (
            <li key={group.id}>
              <Link
                href={`${HOME_FOR_ROLE.doctor}/cases/${group.latest.id}`}
                className="group flex items-start gap-3 border-b border-line px-4 py-3.5 transition-colors duration-150 last:border-b-0 hover:bg-sunken"
              >
                <Avatar name={group.latest.patient.display_name} />
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold text-ink">{group.latest.patient.display_name}</span>
                    <StatusBadge status={group.latest.status} />
                  </span>
                  <span className="block text-small text-muted">{patientMeta(group.latest.patient, t)}</span>
                  <span className="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 text-caption text-subtle">
                    <span className="tabular">{t("patients.consultations", { count: group.items.length })}</span>
                    <span>{t("patients.latest", { date: formatDate(group.latest.created_at) })}</span>
                  </span>
                </span>
                <ArrowRight
                  size={18}
                  aria-hidden
                  className="mt-1 shrink-0 self-start text-subtle transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-brand"
                />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
