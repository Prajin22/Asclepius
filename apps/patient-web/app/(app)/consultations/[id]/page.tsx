"use client";

import { useApi, usePolling, useQuery } from "@carebridge/api-client/react";
import { errorMessage, useI18n } from "@carebridge/i18n";
import type { ConsultationStatus, LanguageCode } from "@carebridge/shared-types";
import { languageInfo } from "@carebridge/shared-types";
import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  CardHeader,
  ErrorState,
  FoldTrack,
  LanguageTag,
  MessageThread,
  PageHeader,
  PrescriptionCard,
  ProvenanceBlock,
  ProvenanceChip,
  SkeletonCard,
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
    <Link href="/consultations" className="inline-flex items-center gap-1.5 font-medium text-brand-strong hover:underline">
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
  if (!q.data) return <SkeletonCard />;
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
        back={back}
        title={c.doctor.name}
        description={`${c.doctor.specialization} · ${t("consultations.requestedOn", { date: formatDate(c.created_at) })}`}
        actions={<StatusBadge status={c.status} />}
      />
      {/* The four folds of a consultation, so the patient can see where this one stands. */}
      {c.status !== "cancelled" ? (
        <FoldTrack
          inline
          className="mb-4"
          label={t("consultations.journeyLabel")}
          current={c.status}
          steps={(["requested", "accepted", "active", "completed"] as const).map((s) => ({
            key: s,
            label: t(`status.${s}`),
          }))}
        />
      ) : null}
      <div className="mb-5">{notice}</div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="flex min-w-0 flex-col gap-5">
          {/* Written by the doctor: inked, attributed, never machine-touched. */}
          <Card tone="ink" aria-labelledby="notes-heading">
            <CardHeader
              id="notes-heading"
              title={t("consultations.doctorNotes")}
              description={t("consultations.independent")}
              action={<ProvenanceChip kind="doctor" />}
            />
            {c.doctor_assessment ? (
              <div>
                <p className="whitespace-pre-line text-body-lg leading-relaxed">{c.doctor_assessment}</p>
                <p className="mt-3 flex items-center gap-2 text-small text-muted">
                  <Avatar name={c.doctor.name} size="sm" tone="ink" />
                  {c.doctor.name} · {c.doctor.specialization}
                </p>
              </div>
            ) : (
              <p className="text-muted">{t("consultations.noNotes")}</p>
            )}
          </Card>

          <section aria-labelledby="rx-heading" className="flex flex-col gap-3">
            <h2 id="rx-heading" className="text-subheading text-ink">
              {t("consultations.prescriptionsTitle")}
            </h2>
            {c.prescriptions.length === 0 ? (
              <p className="rounded-md border border-dashed border-line-strong bg-sunken/70 px-4 py-6 text-center text-muted">
                {t("consultations.noPrescriptions")}
              </p>
            ) : (
              c.prescriptions.map((rx) => <PrescriptionCard key={rx.id} prescription={rx} />)
            )}
          </section>

          <Card aria-labelledby="messages-heading">
            <CardHeader id="messages-heading" title={t("messages.title")} />
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
          <Card aria-labelledby="doctor-heading">
            <div className="flex items-start gap-3">
              <Avatar name={c.doctor.name} size="lg" />
              <div className="min-w-0">
                <h2 id="doctor-heading" className="text-subheading text-ink">
                  {c.doctor.name}
                </h2>
                <p className="text-small text-muted">{c.doctor.specialization}</p>
                <p className="text-small text-muted">{c.doctor.qualification}</p>
              </div>
            </div>
            {c.doctor.clinic_name ? <p className="mt-3 text-body">{c.doctor.clinic_name}</p> : null}
            {c.doctor.clinic_address ? <p className="text-small text-muted">{c.doctor.clinic_address}</p> : null}
            <p className="mt-2 flex flex-wrap gap-1.5">
              {c.doctor.languages.map((code) => (
                <Badge key={code} tone="neutral">
                  <span lang={code}>{languageInfo(code)?.nativeName ?? code}</span>
                </Badge>
              ))}
            </p>
            <div className="mt-3 flex flex-col gap-1 text-small text-muted">
              {c.started_at ? <p>{t("consultations.startedOn", { date: formatDateTime(c.started_at) })}</p> : null}
              {c.completed_at ? <p>{t("consultations.completedOn", { date: formatDateTime(c.completed_at) })}</p> : null}
            </div>
          </Card>

          <Card aria-labelledby="shared-heading">
            <CardHeader id="shared-heading" title={t("consultations.sharedTitle")} />
            {c.shared_categories.length === 0 ? (
              <p className="text-muted">{t("consultations.sharedNothing")}</p>
            ) : (
              <ul className="flex flex-wrap gap-1.5">
                {c.shared_categories.map((cat) => (
                  <li key={cat}>
                    <Badge tone="brand">{t(`shareCategories.${cat}`)}</Badge>
                  </li>
                ))}
              </ul>
            )}
            {c.request_message ? (
              <div className="mt-4">
                <p className="text-small font-semibold text-muted">{t("consultations.yourNote")}</p>
                <ProvenanceBlock
                  kind="original"
                  className="mt-1.5"
                  meta={<LanguageTag code={c.request_language} />}
                >
                  <p lang={c.request_language ?? undefined} className="whitespace-pre-line">
                    {c.request_message}
                  </p>
                </ProvenanceBlock>
              </div>
            ) : null}
          </Card>

          {canCancel ? (
            <div>
              <Button variant="danger" className="w-full sm:w-auto" onClick={cancel}>
                {t("consultations.cancelRequest")}
              </Button>
              {cancelError ? (
                <Alert tone="error" className="mt-2">
                  {errorMessage(t, cancelError)}
                </Alert>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </>
  );
}
