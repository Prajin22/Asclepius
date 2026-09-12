"use client";

import { useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import type { MedicalRecord } from "@carebridge/shared-types";
import {
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  LanguageTag,
  LoadingState,
  PageHeader,
  SourceBadge,
  StatusBadge,
  buttonClasses,
} from "@carebridge/ui";
import Link from "next/link";

function HealthList({ title, records }: { title: string; records: MedicalRecord[] }) {
  const { t } = useI18n();
  return (
    <div>
      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">{title}</h3>
      {records.length === 0 ? (
        <p className="mt-2 text-muted">{t("dashboard.noneRecorded")}</p>
      ) : (
        <ul className="mt-2 flex flex-col gap-2.5">
          {records.map((r) => (
            <li key={r.id}>
              <p className="font-medium leading-snug">{r.title ?? t(`recordType.${r.type}`)}</p>
              <div className="mt-1">
                <SourceBadge source={r.source} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const { t, formatDate } = useI18n();
  const q = useQuery((api) => api.patient.dashboard());

  if (q.error && !q.data) return <ErrorState error={q.error} onRetry={q.reload} />;
  if (!q.data) return <LoadingState />;
  const d = q.data;

  return (
    <>
      <PageHeader
        title={t("dashboard.greeting", { name: d.display_name })}
        description={
          <>
            {t("dashboard.subtitle")}
            {d.age !== null ? <span className="ml-2 text-subtle">· {t("dashboard.age", { age: d.age })}</span> : null}
          </>
        }
      />

      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            title={t("dashboard.currentHealth")}
            action={
              <Link href="/health" className={buttonClasses("ghost", "sm")}>
                {t("dashboard.manageHealth")}
              </Link>
            }
          />
          <div className="grid gap-6 sm:grid-cols-3">
            <HealthList title={t("dashboard.conditions")} records={d.conditions} />
            <HealthList title={t("dashboard.allergies")} records={d.allergies} />
            <HealthList title={t("dashboard.medications")} records={d.medications} />
          </div>
        </Card>

        <Card className="flex flex-col border-brand/30 bg-brand-soft">
          <h2 className="text-lg font-semibold text-brand-strong">{t("dashboard.findDoctor")}</h2>
          <p className="mt-1 flex-1 text-ink">{t("dashboard.findDoctorText")}</p>
          <Link href="/find-care" className={buttonClasses("primary", "lg", "mt-4 w-full")}>
            {t("dashboard.findDoctor")}
          </Link>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader
            title={t("dashboard.currentProblem")}
            action={
              <Link href="/health/current-problem" className={buttonClasses("secondary", "sm")}>
                {t("dashboard.describeProblem")}
              </Link>
            }
          />
          {d.latest_current_problem ? (
            <figure>
              <blockquote
                lang={d.latest_current_problem.source_language}
                className="border-l-4 border-brand/40 pl-4 text-lg leading-relaxed"
              >
                {d.latest_current_problem.content}
              </blockquote>
              <figcaption className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted">
                <SourceBadge source={d.latest_current_problem.source} />
                <LanguageTag code={d.latest_current_problem.source_language} />
                <span>{formatDate(d.latest_current_problem.created_at)}</span>
              </figcaption>
            </figure>
          ) : (
            <EmptyState>{t("dashboard.noProblem")}</EmptyState>
          )}
        </Card>

        <Card>
          <CardHeader
            title={t("dashboard.activeConsultations")}
            action={
              <Link href="/consultations" className={buttonClasses("ghost", "sm")}>
                {t("dashboard.viewAll")}
              </Link>
            }
          />
          {d.open_consultations.length === 0 ? (
            <p className="text-muted">{t("dashboard.noConsultations")}</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {d.open_consultations.map((c) => (
                <li key={c.id}>
                  <Link
                    href={`/consultations/${c.id}`}
                    className="block rounded-lg border border-line px-3.5 py-3 hover:border-brand/40 hover:bg-sunken"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-semibold">{c.doctor.name}</span>
                      <StatusBadge status={c.status} />
                    </div>
                    <p className="text-sm text-muted">{c.doctor.specialization}</p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title={t("dashboard.recentPrescriptions")} />
          {d.recent_prescriptions.length === 0 ? (
            <p className="text-muted">{t("dashboard.noPrescriptions")}</p>
          ) : (
            <ul className="divide-y divide-line">
              {d.recent_prescriptions.map((rx) => (
                <li key={rx.id} className="py-3 first:pt-0 last:pb-0">
                  <Link href={`/consultations/${rx.consultation_id}`} className="group block">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <span className="font-semibold group-hover:underline">{rx.authored_by.name}</span>
                      <span className="text-sm text-muted">
                        {t("prescription.issuedOn", { date: formatDate(rx.created_at) })}
                      </span>
                    </div>
                    <p className="text-sm text-muted">{rx.authored_by.specialization}</p>
                    <p className="mt-1">{rx.items.map((i) => i.medication).join(" · ")}</p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader
            title={t("dashboard.recentDocuments")}
            action={
              <Link href="/documents" className={buttonClasses("ghost", "sm")}>
                {t("dashboard.viewAll")}
              </Link>
            }
          />
          {d.recent_documents.length === 0 ? (
            <p className="text-muted">{t("dashboard.noDocuments")}</p>
          ) : (
            <ul className="flex flex-col gap-2.5">
              {d.recent_documents.map((doc) => (
                <li key={doc.id}>
                  <Link href={`/documents/${doc.id}`} className="block hover:underline">
                    <span className="font-medium">{doc.title || doc.file_name}</span>
                  </Link>
                  <p className="text-sm text-muted">
                    {t(`documentType.${doc.document_type}`)} · {formatDate(doc.uploaded_at)}
                  </p>
                </li>
              ))}
            </ul>
          )}
          <Link href="/documents" className={buttonClasses("secondary", "md", "mt-4 w-full")}>
            {t("dashboard.uploadDocument")}
          </Link>
        </Card>
      </div>
    </>
  );
}
