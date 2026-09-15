"use client";

import { useApi, useQuery } from "@carebridge/api-client/react";
import { errorMessage, useI18n } from "@carebridge/i18n";
import { languageInfo, type DoctorApplicationReview, type DoctorApproval } from "@carebridge/shared-types";
import {
  Alert,
  Avatar,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  PageHeader,
  SegmentedTabs,
  SkeletonCard,
  TextArea,
  cn,
} from "@carebridge/ui";
import { CheckCircle, IdentificationCard, ListChecks, Warning } from "@phosphor-icons/react/dist/ssr";
import { useState, type ReactNode } from "react";

const TABS: DoctorApproval[] = ["pending", "approved", "rejected"];

export default function DoctorApplicationsPage() {
  const { t } = useI18n();
  const q = useQuery((a) => a.admin.doctors());
  const [tab, setTab] = useState<DoctorApproval>("pending");
  const [notice, setNotice] = useState<string | null>(null);

  const all = q.data ?? [];
  const countFor = (status: DoctorApproval) => all.filter((d) => d.approval_status === status).length;

  function reviewed(updated: DoctorApplicationReview) {
    q.setData(all.map((d) => (d.id === updated.id ? updated : d)));
    const key = updated.approval_status === "approved" ? "admin.approvedNotice" : "admin.rejectedNotice";
    setNotice(t(key, { name: updated.name }));
  }

  let list: ReactNode;
  if (q.error && !q.data) {
    list = <ErrorState error={q.error} onRetry={q.reload} />;
  } else if (!q.data) {
    list = <SkeletonCard />;
  } else if (countFor(tab) === 0) {
    list = <EmptyState>{t(`admin.empty.${tab}`)}</EmptyState>;
  } else {
    list = (
      <ul className="flex flex-col gap-4">
        {all
          .filter((d) => d.approval_status === tab)
          .map((d) => (
            <li key={d.id}>
              <ApplicationCard doctor={d} onReviewed={reviewed} />
            </li>
          ))}
      </ul>
    );
  }

  return (
    <>
      <PageHeader title={t("admin.title")} description={t("admin.subtitle")} />
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_19rem]">
        {/* The checklist comes first on a phone, and sits beside the queue on a wide screen. */}
        <Card tone="quiet" aria-labelledby="admin-checklist" className="lg:sticky lg:top-24 lg:col-start-2 lg:row-start-1">
          <h2 id="admin-checklist" className="flex items-center gap-2 text-subheading text-ink">
            <ListChecks size={20} aria-hidden />
            {t("admin.checklist.title")}
          </h2>
          <ol className="mt-3 flex list-decimal flex-col gap-2 pl-5 text-small text-muted marker:font-semibold marker:text-ink">
            <li>{t("admin.checklist.register")}</li>
            <li>{t("admin.checklist.match")}</li>
            <li>{t("admin.checklist.reason")}</li>
          </ol>
        </Card>

        <div className="min-w-0 lg:col-start-1 lg:row-start-1">
          <SegmentedTabs
            label={t("admin.tabs.label")}
            value={tab}
            onChange={(next) => {
              setTab(next);
              setNotice(null);
            }}
            items={TABS.map((status) => ({
              value: status,
              label: t(`admin.tabs.${status}`),
              badge: q.data ? countFor(status) : undefined,
            }))}
          />
          {notice ? (
            <Alert tone="success" className="mt-4">
              {notice}
            </Alert>
          ) : null}
          <div className="mt-4">{list}</div>
        </div>
      </div>
    </>
  );
}

function ApplicationCard({
  doctor,
  onReviewed,
}: {
  doctor: DoctorApplicationReview;
  onReviewed: (updated: DoctorApplicationReview) => void;
}) {
  const api = useApi();
  const { t, formatDate } = useI18n();
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<unknown>(null);

  const status = doctor.approval_status;
  // Rejecting someone already approved takes their access away, so it is worded as such.
  const revoking = status === "approved";
  const headingId = `doctor-${doctor.id}`;

  async function review(kind: "approve" | "reject") {
    setBusy(kind);
    setError(null);
    try {
      const updated =
        kind === "approve"
          ? await api.admin.approveDoctor(doctor.id)
          : await api.admin.rejectDoctor(doctor.id, reason.trim());
      setRejecting(false);
      setReason("");
      onReviewed(updated);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  }

  const clinic = [doctor.clinic_name, doctor.clinic_address].filter(Boolean).join(", ");
  const details: { label: string; value: string | null }[] = [
    { label: t("admin.qualification"), value: doctor.qualification },
    { label: t("admin.email"), value: doctor.email },
    { label: t("admin.phone"), value: doctor.phone },
    { label: t("admin.clinic"), value: clinic || null },
    {
      label: t("admin.languages"),
      value: doctor.languages.map((code) => languageInfo(code)?.englishName ?? code).join(", "),
    },
  ];

  return (
    <Card as="article" aria-labelledby={headingId} padding="none" className="overflow-hidden">
      <div className="flex items-start gap-4 p-5 sm:p-6">
        <Avatar name={doctor.name} className="max-sm:hidden" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h2 id={headingId} className="text-subheading text-ink">
              {doctor.name}
            </h2>
            <p className="text-small text-muted">{t("admin.appliedOn", { date: formatDate(doctor.applied_at) })}</p>
          </div>
          <p className="text-muted">{doctor.specialization}</p>

          {/* The one value checked against the register, set apart from everything else. */}
          <div
            className={cn(
              "mt-4 rounded-md border px-4 py-3",
              doctor.registration_conflict ? "border-warning/40 bg-warning-soft" : "border-line bg-sunken",
            )}
          >
            <p className="flex items-center gap-1.5 text-label uppercase text-subtle">
              <IdentificationCard size={14} aria-hidden />
              {t("admin.registration")}
            </p>
            <p className="mt-1 select-all break-all font-mono text-value text-ink">{doctor.registration_identifier}</p>
            {doctor.registration_conflict ? (
              <p className="mt-1.5 flex items-start gap-1.5 text-small font-medium text-warning">
                <Warning size={16} weight="fill" className="mt-0.5 shrink-0" aria-hidden />
                {t("admin.conflict")}
              </p>
            ) : null}
          </div>

          <dl className="mt-4 grid gap-x-6 gap-y-3 sm:grid-cols-2">
            {details.map((row) => (
              <div key={row.label} className="min-w-0">
                <dt className="text-caption text-subtle">{row.label}</dt>
                <dd className={cn("break-words text-small", row.value ? "text-ink" : "text-subtle")}>
                  {row.value || t("admin.notGiven")}
                </dd>
              </div>
            ))}
          </dl>

          {status !== "pending" && doctor.reviewed_at ? (
            <p className="mt-4 text-small text-muted">{t("admin.reviewedOn", { date: formatDate(doctor.reviewed_at) })}</p>
          ) : null}
          {status === "rejected" && doctor.approval_note ? (
            <div className="mt-2 rounded-md border border-danger/20 bg-danger-soft px-3.5 py-2.5 text-small">
              <p className="font-semibold text-danger">{t("admin.note")}</p>
              <p className="mt-0.5 text-ink">{doctor.approval_note}</p>
            </div>
          ) : null}
        </div>
      </div>

      <div className="border-t border-line bg-canvas px-5 py-4 sm:px-6">
        {rejecting ? (
          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              void review("reject");
            }}
          >
            {revoking ? <Alert tone="warning">{t("admin.revokeWarning")}</Alert> : null}
            <Field label={t("admin.reasonLabel")}>
              {(p) => (
                <TextArea
                  {...p}
                  rows={2}
                  required
                  maxLength={300}
                  autoFocus
                  placeholder={t("admin.reasonPlaceholder")}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
              )}
            </Field>
            {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
            <div className="flex flex-wrap gap-2">
              <Button type="submit" variant="danger" loading={busy === "reject"} disabled={!reason.trim()}>
                {revoking ? t("admin.confirmRevoke") : t("admin.confirmReject")}
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  setRejecting(false);
                  setReason("");
                  setError(null);
                }}
              >
                {t("actions.cancel")}
              </Button>
            </div>
          </form>
        ) : (
          <div className="flex flex-col gap-3">
            {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
            <div className="flex flex-wrap gap-2">
              {status === "approved" ? null : (
                <Button loading={busy === "approve"} onClick={() => void review("approve")}>
                  <CheckCircle size={18} aria-hidden />
                  {t("admin.approve")}
                </Button>
              )}
              {status === "rejected" ? null : (
                <Button
                  variant="danger"
                  disabled={busy !== null}
                  onClick={() => {
                    setRejecting(true);
                    setError(null);
                  }}
                >
                  {revoking ? t("admin.revoke") : t("admin.reject")}
                </Button>
              )}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
