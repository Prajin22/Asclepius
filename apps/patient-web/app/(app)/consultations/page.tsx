"use client";

import { useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import { Avatar, EmptyState, ErrorState, PageHeader, SkeletonCard, StatusBadge, buttonClasses } from "@carebridge/ui";
import { ArrowRight } from "@phosphor-icons/react/dist/ssr";
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
        <SkeletonCard />
      ) : q.data.length === 0 ? (
        <EmptyState
          title={t("consultations.empty")}
          action={
            <Link href="/find-care" className={buttonClasses("primary", "md")}>
              {t("consultations.findDoctor")}
            </Link>
          }
        >
          {t("consultations.emptyWhy")}
        </EmptyState>
      ) : (
        <ul className="flex flex-col gap-3">
          {q.data.map((c) => (
            <li key={c.id}>
              <Link
                href={`/consultations/${c.id}`}
                className="group flex items-start gap-3.5 rounded-md border border-line bg-surface p-4 transition-colors duration-150 hover:border-brand/40 hover:bg-brand-tint sm:p-5"
              >
                <Avatar name={c.doctor.name} size="lg" />
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-start justify-between gap-2">
                    <span className="min-w-0">
                      <span className="block truncate text-subheading text-ink">{c.doctor.name}</span>
                      <span className="block truncate text-small text-muted">{c.doctor.specialization}</span>
                    </span>
                    <StatusBadge status={c.status} />
                  </span>
                  <span className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 text-small text-muted">
                    <span>{t("consultations.requestedOn", { date: formatDate(c.created_at) })}</span>
                    {c.started_at ? <span>{t("consultations.startedOn", { date: formatDate(c.started_at) })}</span> : null}
                    {c.completed_at ? (
                      <span>{t("consultations.completedOn", { date: formatDate(c.completed_at) })}</span>
                    ) : null}
                    <span className="tabular">{t("consultations.prescriptionCount", { count: c.prescription_count })}</span>
                  </span>
                </span>
                <ArrowRight
                  size={18}
                  aria-hidden
                  className="mt-1 shrink-0 text-subtle transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-brand"
                />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
