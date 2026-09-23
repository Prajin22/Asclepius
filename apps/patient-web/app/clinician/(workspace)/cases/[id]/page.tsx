"use client";

import { useApi, usePolling, useQuery } from "@carebridge/api-client/react";
import { errorMessage, useI18n } from "@carebridge/i18n";
import type { CaseView } from "@carebridge/shared-types";
import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  CardHeader,
  ErrorState,
  Field,
  FoldTrack,
  MessageThread,
  PrescriptionCard,
  ProvenanceChip,
  SkeletonCard,
  StatusBadge,
  TextArea,
} from "@carebridge/ui";
import { ArrowLeft } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { CaseSummary } from "@/components/clinician/CaseSummary";
import { PrescriptionForm } from "@/components/clinician/PrescriptionForm";
import { SharedClinicalInfo } from "@/components/clinician/SharedClinicalInfo";
import { patientMeta } from "@/lib/format";
import { HOME_FOR_ROLE } from "@/lib/routes";

function AssessmentEditor({ view, onSave }: { view: CaseView; onSave: (text: string) => Promise<void> }) {
  const { t } = useI18n();
  const [text, setText] = useState(view.doctor_assessment ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => setText(view.doctor_assessment ?? ""), [view.doctor_assessment]);

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError(null);
        setSaved(false);
        try {
          await onSave(text);
          setSaved(true);
        } catch (err) {
          setError(err);
        } finally {
          setBusy(false);
        }
      }}
    >
      <Field label={t("case.assessment")} hint={t("case.assessmentHint")} className="[&>label]:sr-only">
        {(p) => (
          <TextArea
            {...p}
            rows={6}
            maxLength={10000}
            value={text}
            placeholder={t("case.assessmentHint")}
            onChange={(e) => {
              setSaved(false);
              setText(e.target.value);
            }}
          />
        )}
      </Field>
      {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
      {saved ? <Alert tone="success">{t("case.notesSaved")}</Alert> : null}
      <div>
        <Button type="submit" variant="secondary" loading={busy}>
          {busy ? t("actions.saving") : t("case.saveNotes")}
        </Button>
      </div>
    </form>
  );
}

export default function CasePage() {
  const { id } = useParams<{ id: string }>();
  const api = useApi();
  const router = useRouter();
  const { t, formatDateTime } = useI18n();
  const q = useQuery((a) => a.doctor.caseView(id), [id]);
  const status = q.data?.status;
  const canWork = status === "accepted" || status === "active";
  // Poll messages only (the case view itself is audited on every read).
  const messages = useQuery((a) => a.messages.list(id), [id]);
  usePolling(messages.reload, 5000, canWork);

  const [actionError, setActionError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [declining, setDeclining] = useState(false);
  const [reason, setReason] = useState("");

  // The case summary is fetched on its own, so the page renders everything the
  // patient shared without waiting for it. Generation is a separate, explicit
  // action — the doctor decides when to spend it.
  const summary = useQuery((a) => a.doctor.caseSummary(id), [id]);
  const [generatingSummary, setGeneratingSummary] = useState(false);
  const [summaryError, setSummaryError] = useState<unknown>(null);

  async function generateSummary() {
    setGeneratingSummary(true);
    setSummaryError(null);
    try {
      // The frontend sends only the consultation id. Authorization, the source
      // bundle and validation all stay on the server.
      summary.setData(await api.doctor.generateCaseSummary(id));
    } catch (err) {
      setSummaryError(err);
      // Re-read so a failed attempt still shows the stored state and the
      // remaining generation budget.
      void summary.reload();
    } finally {
      setGeneratingSummary(false);
    }
  }

  const back = (
    <Link
      href={`${HOME_FOR_ROLE.doctor}/consultations`}
      className="inline-flex items-center gap-1.5 font-medium text-brand-strong hover:underline"
    >
      <ArrowLeft size={16} aria-hidden />
      {t("case.back")}
    </Link>
  );

  if (q.error && !q.data) {
    return (
      <>
        <div className="mb-4">{back}</div>
        <ErrorState error={q.error} onRetry={q.reload} />
      </>
    );
  }
  if (!q.data) return <SkeletonCard />;
  const v = q.data;

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setActionError(null);
    try {
      await action();
    } catch (err) {
      setActionError(err);
    } finally {
      setBusy(false);
    }
  }

  const accept = () => run(async () => q.setData(await api.doctor.accept(v.id)));
  const complete = () => {
    if (!window.confirm(t("case.confirmComplete"))) return;
    void run(async () => q.setData(await api.doctor.complete(v.id)));
  };
  const decline = () =>
    run(async () => {
      await api.doctor.decline(v.id, reason.trim());
      router.push(`${HOME_FOR_ROLE.doctor}/consultations`);
    });

  return (
    <>
      <div className="mb-4">{back}</div>

      {/* Who this is, where the consultation stands, and what the doctor can do next. */}
      <section aria-label={v.patient.display_name} className="rounded-md border border-line bg-surface p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 gap-4">
            <Avatar name={v.patient.display_name} size="lg" />
            <div className="min-w-0">
              <h1 className="text-page tracking-tight text-ink">{v.patient.display_name}</h1>
              <p className="mt-0.5 text-muted">{patientMeta(v.patient, t)}</p>
              <p className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-small text-muted">
                <span>{t("case.requestedOn", { date: formatDateTime(v.created_at) })}</span>
                {v.started_at ? <span>{t("case.startedOn", { date: formatDateTime(v.started_at) })}</span> : null}
                {v.completed_at ? <span>{t("case.completedOn", { date: formatDateTime(v.completed_at) })}</span> : null}
              </p>
            </div>
          </div>
          <div className="flex flex-col items-start gap-3 sm:items-end">
            <StatusBadge status={v.status} />
            {v.status === "requested" ? (
              <div className="flex flex-wrap gap-2">
                <Button onClick={accept} disabled={busy}>
                  {t("case.accept")}
                </Button>
                <Button variant="danger" onClick={() => setDeclining((d) => !d)} disabled={busy} aria-expanded={declining}>
                  {t("case.decline")}
                </Button>
              </div>
            ) : null}
            {canWork ? (
              <Button variant="secondary" onClick={complete} disabled={busy}>
                {t("case.complete")}
              </Button>
            ) : null}
          </div>
        </div>

        {v.status !== "cancelled" ? (
          <FoldTrack
            inline
            className="mt-4 border-t border-line pt-4"
            label={t("case.journeyLabel")}
            current={v.status}
            steps={(["requested", "accepted", "active", "completed"] as const).map((s) => ({
              key: s,
              label: t(`status.${s}`),
            }))}
          />
        ) : null}

        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-4">
          <span className="text-label uppercase text-subtle">{t("case.sharedScope")}</span>
          {v.shared_categories.length === 0 ? (
            <Badge>{t("case.identityOnly")}</Badge>
          ) : (
            v.shared_categories.map((c) => (
              <Badge key={c} tone="brand">
                {t(`case.categories.${c}`)}
              </Badge>
            ))
          )}
        </div>

        {v.status === "requested" ? <p className="mt-3 text-small text-muted">{t("case.reviewBeforeAccept")}</p> : null}
        {declining ? (
          <div className="mt-4 flex flex-col gap-3 rounded-md border border-danger/30 bg-danger-soft/60 p-4">
            <Field label={t("case.declineReason")}>
              {(p) => <TextArea {...p} rows={2} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} />}
            </Field>
            <div>
              <Button variant="danger" onClick={decline} disabled={busy}>
                {t("case.confirmDecline")}
              </Button>
            </div>
          </div>
        ) : null}
        {actionError ? (
          <Alert tone="error" className="mt-3">
            {errorMessage(t, actionError)}
          </Alert>
        ) : null}
      </section>

      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,27rem)]">
        <div className="flex min-w-0 flex-col gap-5">
          {/* The summary organises what is below it, so it reads first — but it is
              fetched separately, so the case never waits on it, and it sits in the
              shared-information column rather than the doctor's own workspace. */}
          <CaseSummary
            summary={summary.data}
            loading={summary.loading}
            error={summaryError ?? summary.error}
            generating={generatingSummary}
            onGenerate={generateSummary}
          />

          {/* What the patient shared, in the order a consultation actually runs. */}
          <SharedClinicalInfo
            view={v}
            loadDocument={(docId) => api.doctor.documentFile(v.id, docId)}
            loadPage={(docId, page) => api.doctor.documentPageImage(v.id, docId, page)}
          />
        </div>

        {/* The doctor's own work, inked so it is never mistaken for machine output.
            One column in the order they work: assessment, prescriptions, messages.
            Nothing is pinned, so no panel can float over the form beneath it. */}
        <div className="flex min-w-0 flex-col gap-5">
          {v.status === "requested" ? <Alert tone="warning">{t("case.acceptFirst")}</Alert> : null}
          {v.status === "completed" ? <Alert tone="info">{t("case.readOnly")}</Alert> : null}

          <Card tone="ink" aria-labelledby="assessment-heading">
            <CardHeader id="assessment-heading" title={t("case.assessment")} action={<ProvenanceChip kind="doctor" />} />
            {canWork ? (
              <AssessmentEditor
                view={v}
                onSave={async (text) => {
                  q.setData(await api.doctor.setAssessment(v.id, text));
                }}
              />
            ) : v.doctor_assessment ? (
              <p className="whitespace-pre-line">{v.doctor_assessment}</p>
            ) : (
              <p className="text-muted">{t("case.noNotes")}</p>
            )}
          </Card>

          <section aria-labelledby="rx-heading" className="flex flex-col gap-3">
            <h2 id="rx-heading" className="text-heading text-ink">
              {t("case.prescriptions")}
            </h2>
            {v.prescriptions.length === 0 ? (
              <p className="rounded-md border border-dashed border-line-strong bg-sunken/70 px-4 py-5 text-small text-muted">
                {t("case.noPrescriptions")}
              </p>
            ) : (
              v.prescriptions.map((rx) => <PrescriptionCard key={rx.id} prescription={rx} />)
            )}
          </section>

          {v.status === "active" ? (
            <Card tone="ink" aria-labelledby="new-rx-heading">
              <CardHeader
                id="new-rx-heading"
                title={t("case.newPrescription")}
                description={t("case.authorNotice")}
                action={<ProvenanceChip kind="doctor" />}
              />
              <PrescriptionForm
                onSubmit={async (data) => {
                  await api.doctor.createPrescription(v.id, data);
                  await q.reload();
                }}
              />
            </Card>
          ) : null}

          <Card aria-labelledby="messages-heading">
            <CardHeader id="messages-heading" title={t("messages.title")} />
            <MessageThread
              messages={messages.data ?? v.messages}
              viewerRole="doctor"
              canSend={canWork}
              onSend={async (body) => {
                await api.messages.send(v.id, body, null);
                await messages.reload();
              }}
            />
          </Card>
        </div>
      </div>
    </>
  );
}
