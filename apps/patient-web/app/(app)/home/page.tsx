"use client";

import { useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import type { MedicalRecord } from "@carebridge/shared-types";
import {
  Avatar,
  Card,
  CardHeader,
  ErrorState,
  LanguageTag,
  PageHeader,
  ProvenanceBlock,
  ProvenanceChip,
  SkeletonCard,
  SourceBadge,
  StatusBadge,
  buttonClasses,
  cn,
} from "@carebridge/ui";
import { ArrowRight, ChatCircleDots, FileArrowUp, MagnifyingGlass, PencilSimpleLine } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";

/** The three things a patient actually comes here to do. */
function QuickActions() {
  const { t } = useI18n();
  const actions = [
    { href: "/health/current-problem", label: t("dashboard.describeProblem"), Icon: PencilSimpleLine, primary: true },
    { href: "/documents", label: t("dashboard.uploadDocument"), Icon: FileArrowUp },
    { href: "/find-care", label: t("dashboard.findDoctor"), Icon: MagnifyingGlass },
  ];
  return (
    <nav aria-label={t("dashboard.currentHealth")} className="grid gap-2.5 sm:grid-cols-3">
      {actions.map(({ href, label, Icon, primary }) => (
        <Link
          key={href}
          href={href}
          className={cn(
            "flex min-h-16 items-center gap-3 rounded-xl border px-4 py-3 font-semibold transition-colors duration-150",
            primary
              ? "border-brand bg-brand text-white hover:bg-brand-strong"
              : "border-line bg-surface text-ink hover:border-brand/40 hover:bg-brand-tint",
          )}
        >
          <Icon size={22} weight="regular" aria-hidden />
          <span className="min-w-0 text-body">{label}</span>
          <ArrowRight size={16} aria-hidden className="ml-auto opacity-70" />
        </Link>
      ))}
    </nav>
  );
}

function HealthColumn({ title, records }: { title: string; records: MedicalRecord[] }) {
  const { t } = useI18n();
  return (
    <div>
      <h3 className="text-small font-semibold text-muted">{title}</h3>
      {records.length === 0 ? (
        <p className="mt-2 text-small text-muted">{t("dashboard.noneRecorded")}</p>
      ) : (
        <ul className="mt-2 flex flex-col gap-3">
          {records.map((r) => (
            <li key={r.id} className="flex flex-col items-start gap-1">
              <span className="font-medium leading-snug text-ink">{r.title ?? t(`recordType.${r.type}`)}</span>
              <SourceBadge source={r.source} />
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
  if (!q.data) {
    return (
      <div className="flex flex-col gap-5">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }
  const d = q.data;

  return (
    <>
      <PageHeader
        title={t("dashboard.greeting", { name: d.display_name })}
        description={t("dashboard.subtitle")}
      />

      <QuickActions />

      {/* Two independent stacks on a wide screen, so each card keeps its own height without
          leaving a gap beside a taller neighbour. On a phone the stacks dissolve and the
          cards interleave in order of what a patient checks first. */}
      <div className="mt-5 grid items-start gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="flex min-w-0 flex-col gap-5 max-lg:contents">
          <Card className="max-lg:order-1" aria-labelledby="problem-heading">
            <CardHeader
              id="problem-heading"
              title={t("dashboard.currentProblem")}
              action={
                <Link href="/health/current-problem" className={buttonClasses("secondary", "sm")}>
                  {d.latest_current_problem ? t("actions.edit") : t("dashboard.describeProblem")}
                </Link>
              }
            />
            {d.latest_current_problem ? (
              <ProvenanceBlock
                kind="original"
                lang={d.latest_current_problem.source_language}
                meta={
                  <span className="flex flex-wrap items-center gap-2">
                    <LanguageTag code={d.latest_current_problem.source_language} />
                    <span>{formatDate(d.latest_current_problem.created_at)}</span>
                  </span>
                }
              >
                <p className="whitespace-pre-line text-body-lg leading-relaxed">{d.latest_current_problem.content}</p>
              </ProvenanceBlock>
            ) : (
              <div className="rounded-lg border border-dashed border-line-strong bg-sunken/60 px-4 py-6 text-center">
                <p className="text-muted">{t("dashboard.noProblem")}</p>
                <Link href="/health/current-problem" className={buttonClasses("primary", "md", "mt-3")}>
                  {t("dashboard.describeProblem")}
                </Link>
              </div>
            )}
          </Card>

          <Card className="max-lg:order-3" aria-labelledby="health-heading">
            <CardHeader
              id="health-heading"
              title={t("dashboard.currentHealth")}
              action={
                <Link href="/health" className={buttonClasses("ghost", "sm")}>
                  {t("dashboard.manageHealth")}
                </Link>
              }
            />
            {/* Columns follow the card's own width, so source badges never squeeze onto two lines. */}
            <div className="@container">
              <div className="grid gap-5 @sm:grid-cols-2 @xl:grid-cols-3">
                <HealthColumn title={t("dashboard.conditions")} records={d.conditions} />
                <HealthColumn title={t("dashboard.allergies")} records={d.allergies} />
                <HealthColumn title={t("dashboard.medications")} records={d.medications} />
              </div>
            </div>
          </Card>

          <Card className="max-lg:order-5" aria-labelledby="prescriptions-heading">
            <CardHeader id="prescriptions-heading" title={t("dashboard.recentPrescriptions")} />
            {d.recent_prescriptions.length === 0 ? (
              <p className="text-small text-muted">{t("dashboard.noPrescriptions")}</p>
            ) : (
              <ul className="grid gap-3 sm:grid-cols-2">
                {d.recent_prescriptions.map((rx) => (
                  <li key={rx.id}>
                    <Link
                      href={`/consultations/${rx.consultation_id}`}
                      className="flex h-full flex-col rounded-lg border-l-[3px] border border-line border-l-ink bg-surface px-4 py-3 transition-colors duration-150 hover:bg-sunken"
                    >
                      <span className="flex flex-wrap items-center justify-between gap-2">
                        <ProvenanceChip kind="doctor" label={rx.authored_by.name} />
                        <span className="text-small text-muted">
                          {t("prescription.issuedOn", { date: formatDate(rx.created_at) })}
                        </span>
                      </span>
                      <span className="mt-2 text-body text-ink">{rx.items.map((i) => i.medication).join(" · ")}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        <div className="flex min-w-0 flex-col gap-5 max-lg:contents">
          <Card className="max-lg:order-2" aria-labelledby="consultations-heading">
            <CardHeader
              id="consultations-heading"
              title={t("dashboard.activeConsultations")}
              action={
                <Link href="/consultations" className={buttonClasses("ghost", "sm")}>
                  {t("dashboard.viewAll")}
                </Link>
              }
            />
            {d.open_consultations.length === 0 ? (
              <div className="rounded-lg border border-dashed border-line-strong bg-sunken/60 px-4 py-5 text-center text-small text-muted">
                <ChatCircleDots size={22} aria-hidden className="mx-auto mb-1.5 text-subtle" />
                {t("dashboard.noConsultations")}
              </div>
            ) : (
              <ul className="flex flex-col gap-2">
                {d.open_consultations.map((c) => (
                  <li key={c.id}>
                    <Link
                      href={`/consultations/${c.id}`}
                      className="flex items-start gap-3 rounded-lg border border-line px-3 py-3 transition-colors duration-150 hover:border-brand/40 hover:bg-brand-tint"
                    >
                      <Avatar name={c.doctor.name} size="sm" />
                      {/* The status sits under the name, so a narrow column never truncates who the doctor is. */}
                      <span className="min-w-0 flex-1">
                        <span className="block font-semibold leading-snug text-ink">{c.doctor.name}</span>
                        <span className="block text-small text-muted">{c.doctor.specialization}</span>
                        <span className="mt-2 block">
                          <StatusBadge status={c.status} />
                        </span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card className="max-lg:order-4" aria-labelledby="documents-heading">
            <CardHeader
              id="documents-heading"
              title={t("dashboard.recentDocuments")}
              action={
                <Link href="/documents" className={buttonClasses("ghost", "sm")}>
                  {t("dashboard.viewAll")}
                </Link>
              }
            />
            {d.recent_documents.length === 0 ? (
              <div className="rounded-lg border border-dashed border-line-strong bg-sunken/60 px-4 py-5 text-center text-small text-muted">
                {t("dashboard.noDocuments")}
              </div>
            ) : (
              <ul className="flex flex-col gap-2.5">
                {d.recent_documents.map((doc) => (
                  <li key={doc.id}>
                    <Link href={`/documents/${doc.id}`} className="group block">
                      <span className="block truncate font-medium text-ink group-hover:underline">
                        {doc.title || doc.file_name}
                      </span>
                      <span className="mt-1 flex flex-wrap items-center gap-2 text-small text-muted">
                        <ProvenanceChip kind="document" label={t(`documentType.${doc.document_type}`)} />
                        {formatDate(doc.uploaded_at)}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            <Link href="/documents" className={buttonClasses("secondary", "md", "mt-4 w-full")}>
              {t("dashboard.uploadDocument")}
            </Link>
          </Card>
        </div>
      </div>
    </>
  );
}
