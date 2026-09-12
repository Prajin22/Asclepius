"use client";

import { useApi, usePolling, useQuery } from "@carebridge/api-client/react";
import { errorMessage, useI18n } from "@carebridge/i18n";
import type { ConsultationStatus, LanguageCode } from "@carebridge/shared-types";
import { languageInfo } from "@carebridge/shared-types";
import {
  Alert,
  Button,
  Card,
  CardHeader,
  ErrorState,
  LanguageTag,
  LoadingState,
  MessageThread,
  PageHeader,
  PrescriptionCard,
  StatusBadge,
} from "@carebridge/ui";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ArrowLeftIcon } from "@/components/icons";

const OPEN: ConsultationStatus[] = ["requested", "accepted", "active"];

export default function ConsultationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const api = useApi();
  const { t, formatDate, formatDateTime, locale } = useI18n();
  const q = useQuery((a) => a.patient.consultation(id), [id]);
  const [cancelError, setCancelError] = useState<unknown>(null);
  usePolling(q.reload, 5000, q.data ? OPEN.includes(q.data.status) : false);

  const back = (
    <Link href="/consultations" className="inline-flex items-center gap-1.5 font-medium text-brand hover:underline">
      <ArrowLeftIcon />
      {t("consultations.back")}
    </Link>
  );

  if (q.error && !q.data) {
    return (
      <>
        {back}
        <ErrorState error={q.error} onRetry={q.reload} />
      </>
    );
  }
  if (!q.data) return <LoadingState />;
  const c = q.data;
  const canMessage = c.status === "accepted" || c.status === "active";
  const canCancel = c.status === "requested" || c.status === "accepted";

  const notice = {
    requested: <Alert tone="warning">{t("consultations.waiting", { name: c.doctor.name })}</Alert>,
    accepted: <Alert tone="success">{t("consultations.active")}</Alert>,
    active: <Alert tone="success">{t("consultations.active")}</Alert>,
    completed: <Alert tone="info">{t("consultations.completed")}</Alert>,
    cancelled: (
      <Alert tone="error" title={t("consultations.cancelled")}>
        {c.cancellation_reason}
      </Alert>
    ),
  }[c.status];

  async function cancel() {
    if (!window.confirm(t("consultations.confirmCancel"))) return;
    setCancelError(null);
    try {
      q.setData(await api.patient.cancelConsultation(c.id));
    } catch (err) {
      setCancelError(err);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow={back}
        title={c.doctor.name}
        description={`${c.doctor.specialization} · ${t("consultations.requestedOn", { date: formatDate(c.created_at) })}`}
        actions={<StatusBadge status={c.status} />}
      />
      <div className="mb-5">{notice}</div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="flex min-w-0 flex-col gap-5">
          <Card>
            <CardHeader
              title={t("consultations.doctorNotes")}
              description={t("consultations.independent")}
            />
            {c.doctor_assessment ? (
              <div>
                <p className="whitespace-pre-line leading-relaxed">{c.doctor_assessment}</p>
                <p className="mt-2 text-sm text-muted">— {c.doctor.name}</p>
              </div>
            ) : (
              <p className="text-muted">{t("consultations.noNotes")}</p>
            )}
          </Card>

          <section aria-labelledby="rx-heading" className="flex flex-col gap-3">
            <h2 id="rx-heading" className="text-lg font-semibold">
              {t("consultations.prescriptionsTitle")}
            </h2>
            {c.prescriptions.length === 0 ? (
              <p className="rounded-xl border border-line bg-surface p-5 text-muted">{t("consultations.noPrescriptions")}</p>
            ) : (
              c.prescriptions.map((rx) => <PrescriptionCard key={rx.id} prescription={rx} />)
            )}
          </section>

          <Card>
            <CardHeader title={t("messages.title")} />
            <MessageThread
              messages={c.messages}
              viewerRole="patient"
              canSend={canMessage}
              composeLanguage={locale as LanguageCode}
              onSend={async (body) => {
                await api.messages.send(c.id, body, locale as LanguageCode);
                await q.reload();
              }}
            />
          </Card>
        </div>

        <div className="flex min-w-0 flex-col gap-5">
          <Card>
            <p className="font-semibold">{c.doctor.name}</p>
            <p className="text-muted">{c.doctor.qualification}</p>
            <p className="text-muted">{c.doctor.specialization}</p>
            {c.doctor.clinic_name ? <p className="mt-2">{c.doctor.clinic_name}</p> : null}
            {c.doctor.clinic_address ? <p className="text-sm text-muted">{c.doctor.clinic_address}</p> : null}
            <p className="mt-2 text-sm text-muted">
              {c.doctor.languages.map((code) => languageInfo(code)?.nativeName).join(" · ")}
            </p>
            <dl className="mt-3 flex flex-col gap-1 text-sm">
              {c.started_at ? (
                <div className="flex gap-2">
                  <dd>{t("consultations.startedOn", { date: formatDateTime(c.started_at) })}</dd>
                </div>
              ) : null}
              {c.completed_at ? (
                <div className="flex gap-2">
                  <dd>{t("consultations.completedOn", { date: formatDateTime(c.completed_at) })}</dd>
                </div>
              ) : null}
            </dl>
          </Card>

          <Card>
            <CardHeader title={t("consultations.sharedTitle")} />
            {c.shared_categories.length === 0 ? (
              <p className="text-muted">{t("consultations.sharedNothing")}</p>
            ) : (
              <ul className="flex flex-col gap-1.5">
                {c.shared_categories.map((cat) => (
                  <li key={cat} className="flex items-center gap-2">
                    <span aria-hidden className="size-2 rounded-full bg-brand" />
                    {t(`shareCategories.${cat}`)}
                  </li>
                ))}
              </ul>
            )}
            {c.request_message ? (
              <div className="mt-4 border-t border-line pt-3">
                <p className="text-sm font-semibold text-muted">{t("consultations.yourNote")}</p>
                <p lang={c.request_language ?? undefined} className="mt-1 whitespace-pre-line">
                  {c.request_message}
                </p>
                <LanguageTag code={c.request_language} />
              </div>
            ) : null}
          </Card>

          {canCancel ? (
            <div>
              <Button variant="danger" onClick={cancel}>
                {t("consultations.cancelRequest")}
              </Button>
              {cancelError ? <Alert tone="error" className="mt-2">{errorMessage(t, cancelError)}</Alert> : null}
            </div>
          ) : null}
        </div>
      </div>
    </>
  );
}
