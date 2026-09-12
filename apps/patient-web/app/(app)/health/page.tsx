"use client";

import { useApi, useQuery } from "@carebridge/api-client/react";
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
  Badge,
  buttonClasses,
} from "@carebridge/ui";
import Link from "next/link";
import { RecordSection, SourceLegend, type EditableType, type RecordFormValues } from "@/components/records";

const SECTIONS: { key: string; addType?: EditableType; match: (r: MedicalRecord) => boolean }[] = [
  { key: "conditions", addType: "condition", match: (r) => r.type === "condition" && r.status === "active" },
  { key: "allergies", addType: "allergy", match: (r) => r.type === "allergy" },
  { key: "medications", addType: "medication", match: (r) => r.type === "medication" },
  { key: "history", addType: "history_note", match: (r) => r.type === "history_note" },
  // A relative's conditions live apart from the patient's own history.
  { key: "family", addType: "family_history", match: (r) => r.type === "family_history" },
  { key: "past", match: (r) => r.type === "condition" && r.status === "resolved" },
];

export default function MyHealthPage() {
  const api = useApi();
  const { t, formatDate } = useI18n();
  const q = useQuery((a) => a.patient.records());

  if (q.error && !q.data) return <ErrorState error={q.error} onRetry={q.reload} />;
  if (!q.data) return <LoadingState />;
  const records = q.data;
  const problems = records.filter((r) => r.type === "current_problem");

  const onUpdate = async (id: string, values: RecordFormValues) => {
    await api.patient.updateRecord(id, values);
    await q.reload();
  };
  const onDelete = async (id: string) => {
    await api.patient.deleteRecord(id);
    await q.reload();
  };

  return (
    <>
      <PageHeader
        title={t("health.title")}
        description={t("health.subtitle")}
        actions={
          <Link href="/health/current-problem" className={buttonClasses("primary", "md")}>
            {t("health.describeProblem")}
          </Link>
        }
      />
      <div className="mb-6 rounded-xl border border-line bg-surface px-4 py-3.5">
        <SourceLegend />
        <p className="mt-2 text-small text-muted">{t("health.doctorLocked")}</p>
      </div>

      {/* Two balanced columns of sections on a wide screen; cards of different lengths leave no holes. */}
      <div className="gap-5 xl:columns-2 [&>*]:mb-5 [&>*]:break-inside-avoid">
        {SECTIONS.map((s) => (
          <RecordSection
            key={s.key}
            title={t(`health.sections.${s.key}`)}
            records={records.filter(s.match)}
            addType={s.addType}
            onCreate={async (data) => {
              await api.patient.createRecord(data);
              await q.reload();
            }}
            onUpdate={onUpdate}
            onDelete={onDelete}
          />
        ))}

        <Card>
          <CardHeader
            title={t("health.sections.problems")}
            action={
              <Link href="/health/current-problem" className={buttonClasses("secondary", "sm")}>
                {t("health.add")}
              </Link>
            }
          />
          {problems.length === 0 ? (
            <EmptyState>{t("health.empty")}</EmptyState>
          ) : (
            <ul className="divide-y divide-line">
              {problems.map((p) => (
                <li key={p.id} className="py-3.5 first:pt-0 last:pb-0">
                  <p lang={p.source_language} className="whitespace-pre-line">
                    {p.content}
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <SourceBadge source={p.source} />
                    {p.status === "resolved" ? <Badge>{t("recordStatus.resolved")}</Badge> : null}
                    <LanguageTag code={p.source_language} />
                    <span className="text-caption text-muted">{t("health.recorded", { date: formatDate(p.created_at) })}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
