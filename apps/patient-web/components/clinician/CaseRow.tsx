"use client";

import { useI18n } from "@carebridge/i18n";
import type { DoctorQueueItem } from "@carebridge/shared-types";
import { Avatar, EmptyState, StatusBadge } from "@carebridge/ui";
import { ArrowRight } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { patientMeta } from "@/lib/format";
import { HOME_FOR_ROLE } from "@/lib/routes";

/**
 * One case in a list: who it is, where it stands, and the patient's own words in
 * their own material, so the doctor reads the person before the machine.
 */
export function CaseRow({ item, dateLabel }: { item: DoctorQueueItem; dateLabel: string }) {
  const { t } = useI18n();
  return (
    <li>
      <Link
        href={`${HOME_FOR_ROLE.doctor}/cases/${item.id}`}
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
            <span className="mt-1.5 line-clamp-2 block rounded-md border border-paper-line bg-paper px-3 py-1.5 text-small text-paper-ink">
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

export function QueueList({
  items,
  empty,
  emptyWhy,
  dateOf,
}: {
  items: DoctorQueueItem[];
  empty: string;
  emptyWhy?: string;
  dateOf: (item: DoctorQueueItem) => string;
}) {
  if (items.length === 0) {
    return emptyWhy ? <EmptyState title={empty}>{emptyWhy}</EmptyState> : <EmptyState>{empty}</EmptyState>;
  }
  return (
    <ul className="overflow-hidden rounded-md border border-line bg-surface">
      {items.map((item) => (
        <CaseRow key={item.id} item={item} dateLabel={dateOf(item)} />
      ))}
    </ul>
  );
}
