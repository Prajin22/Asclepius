"use client";

import { useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import { EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge, buttonClasses } from "@carebridge/ui";
import Link from "next/link";

export default function ConsultationsPage() {
  const { t, formatDate } = useI18n();
  const q = useQuery((a) => a.patient.consultations());

  return (
    <>
      <PageHeader title={t("consultations.title")} description={t("consultations.subtitle")} />
      {q.error && !q.data ? (
        <ErrorState error={q.error} onRetry={q.reload} />
      ) : !q.data ? (
        <LoadingState />
      ) : q.data.length === 0 ? (
        <EmptyState
          action={
            <Link href="/find-care" className={buttonClasses("primary", "md")}>
              {t("consultations.findDoctor")}
            </Link>
          }
        >
          {t("consultations.empty")}
        </EmptyState>
      ) : (
        <ul className="flex flex-col gap-3">
          {q.data.map((c) => (
            <li key={c.id}>
              <Link
                href={`/consultations/${c.id}`}
                className="block rounded-xl border border-line bg-surface p-4 hover:border-brand/40 sm:p-5"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-lg font-semibold">{c.doctor.name}</p>
                    <p className="text-muted">{c.doctor.specialization}</p>
                  </div>
                  <StatusBadge status={c.status} />
                </div>
                <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted">
                  <span>{t("consultations.requestedOn", { date: formatDate(c.created_at) })}</span>
                  {c.started_at ? <span>{t("consultations.startedOn", { date: formatDate(c.started_at) })}</span> : null}
                  {c.completed_at ? (
                    <span>{t("consultations.completedOn", { date: formatDate(c.completed_at) })}</span>
                  ) : null}
                  <span>{t("consultations.prescriptionCount", { count: c.prescription_count })}</span>
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
