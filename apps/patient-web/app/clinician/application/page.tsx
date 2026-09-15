"use client";

import { useApi, useAuth, useQuery } from "@carebridge/api-client/react";
import { errorMessage, useI18n } from "@carebridge/i18n";
import { languageInfo, type DoctorAccount, type DoctorApproval } from "@carebridge/shared-types";
import { Alert, Button, Card, CardHeader, ErrorState, LoadingState, Logo, buttonClasses, cn } from "@carebridge/ui";
import { CheckCircle, Hourglass, LockSimple, SignOut, XCircle } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import {
  DoctorDetailsFields,
  detailsFromDraft,
  draftFromAccount,
  isDraftComplete,
  type DoctorDetailsDraft,
} from "@/components/DoctorDetailsFields";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { HOME_FOR_ROLE } from "@/lib/routes";

const STATUS_ICON = { pending: Hourglass, approved: CheckCircle, rejected: XCircle } as const;

const STATUS_SURFACE: Record<DoctorApproval, string> = {
  pending: "border-warning/30 bg-warning-soft text-warning",
  approved: "border-success/25 bg-success-soft text-success",
  rejected: "border-danger/30 bg-danger-soft text-danger",
};

const STEPS = ["submitted", "review", "access"] as const;

/**
 * Where a doctor waits before approval. It reads only the doctor's own
 * application; nothing here can reach patient information.
 */
export default function DoctorApplicationPage() {
  const { session, ready, logout } = useAuth();
  const router = useRouter();
  const { t } = useI18n();
  const isDoctor = session?.user.role === "doctor";

  useEffect(() => {
    if (!ready) return;
    if (!session) router.replace("/login");
    else if (session.user.role !== "doctor") router.replace(HOME_FOR_ROLE[session.user.role]);
  }, [ready, session, router]);

  return (
    <div className="flex min-h-[100dvh] flex-col">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-16 max-w-3xl items-center justify-between gap-3 px-4 sm:px-6">
          <p className="flex items-center gap-2.5 text-subheading tracking-tight text-brand-strong">
            <Logo size={26} />
            {t("app.name")}
          </p>
          <div className="flex items-center gap-2">
            <LanguageSwitcher />
            {session ? (
              <Button variant="ghost" size="sm" onClick={logout} className="max-sm:px-2.5">
                <SignOut size={18} aria-hidden />
                <span className="max-sm:sr-only">{t("actions.signOut")}</span>
              </Button>
            ) : null}
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-3xl flex-1 px-4 py-6 sm:px-6 lg:py-10">
        {ready && isDoctor ? <ApplicationStatus /> : <LoadingState />}
      </main>
    </div>
  );
}

function ApplicationStatus() {
  const api = useApi();
  const { t } = useI18n();
  const q = useQuery((a) => a.doctor.profile());
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<DoctorDetailsDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [resubmitted, setResubmitted] = useState(false);

  if (q.error && !q.data) return <ErrorState error={q.error} onRetry={q.reload} />;
  if (!q.data) return <LoadingState />;

  const account = q.data;
  const status = account.approval_status;
  const Icon = STATUS_ICON[status];
  // A rejected application is corrected in place; a pending one only when the doctor asks.
  const formOpen = status === "rejected" || (status === "pending" && editing);
  const current = draft ?? draftFromAccount(account);

  async function resubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setResubmitted(false);
    try {
      q.setData(await api.doctor.updateApplication(detailsFromDraft(current)));
      setEditing(false);
      setDraft(null);
      setResubmitted(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const cancelEdit = () => {
    setEditing(false);
    setDraft(null);
    setError(null);
  };

  return (
    <>
      <h1 className="text-title text-ink">{t("application.title")}</h1>

      <section aria-live="polite" className={cn("mt-6 flex gap-4 rounded-md border p-5 sm:p-6", STATUS_SURFACE[status])}>
        <Icon size={28} weight="duotone" className="shrink-0" aria-hidden />
        <div className="min-w-0 flex-1">
          <h2 className="text-subheading">{t(`application.status.${status}`)}</h2>
          <p className="mt-1 text-ink/80">{t(`application.${status}Body`)}</p>
          {status === "rejected" && account.approval_note ? (
            <div className="mt-3 rounded-md border border-danger/20 bg-surface px-3.5 py-2.5">
              <p className="text-label uppercase text-subtle">{t("application.reason")}</p>
              <p className="mt-1 text-ink">{account.approval_note}</p>
            </div>
          ) : null}
          {status === "approved" ? (
            <Link href={HOME_FOR_ROLE.doctor} className={buttonClasses("primary", "md", "mt-4")}>
              {t("application.open")}
            </Link>
          ) : null}
          {status === "pending" ? (
            <Button variant="secondary" size="sm" className="mt-4" loading={q.loading} onClick={() => void q.reload()}>
              {t("application.checkAgain")}
            </Button>
          ) : null}
        </div>
      </section>

      <ol aria-label={t("application.steps.label")} className="mt-5 grid gap-2.5 sm:grid-cols-3">
        {STEPS.map((step, i) => {
          const done = i === 0 || status === "approved";
          const now = !done && i === 1;
          return (
            <li
              key={step}
              aria-current={now ? "step" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-md border px-3.5 py-3",
                done || now ? "border-line-strong bg-surface" : "border-line bg-sunken/60",
              )}
            >
              {done ? (
                <CheckCircle size={20} weight="fill" className="shrink-0 text-success" aria-hidden />
              ) : (
                <span
                  aria-hidden
                  className={cn(
                    "tabular grid size-5 shrink-0 place-items-center rounded-full border-2 text-[0.625rem] font-semibold",
                    now ? "border-brand text-brand-strong" : "border-line-strong text-subtle",
                  )}
                >
                  {i + 1}
                </span>
              )}
              <span className={cn("text-small font-medium", done || now ? "text-ink" : "text-muted")}>
                {t(`application.steps.${step}`)}
              </span>
            </li>
          );
        })}
      </ol>

      {status === "approved" ? null : (
        <p className="mt-4 flex gap-2 text-small text-muted">
          <LockSimple size={16} className="mt-0.5 shrink-0" aria-hidden />
          {t("application.privacy")}
        </p>
      )}

      {resubmitted ? (
        <Alert tone="success" className="mt-6">
          {t("application.resubmitted")}
        </Alert>
      ) : null}

      <Card className="mt-6" aria-labelledby="application-details">
        <CardHeader
          id="application-details"
          title={t("application.submitted")}
          action={
            status === "pending" && !editing ? (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setEditing(true);
                  setResubmitted(false);
                }}
              >
                {t("application.edit")}
              </Button>
            ) : null
          }
        />
        {formOpen ? (
          <form onSubmit={resubmit} className="flex flex-col gap-5">
            <DoctorDetailsFields value={current} onChange={setDraft} />
            {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
            <div className="flex flex-wrap gap-2">
              <Button type="submit" loading={busy} disabled={!isDraftComplete(current)}>
                {busy ? t("application.resubmitting") : t("application.resubmit")}
              </Button>
              {editing ? (
                <Button variant="ghost" onClick={cancelEdit}>
                  {t("actions.cancel")}
                </Button>
              ) : null}
            </div>
          </form>
        ) : (
          <SubmittedDetails account={account} />
        )}
      </Card>
    </>
  );
}

function SubmittedDetails({ account }: { account: DoctorAccount }) {
  const { t } = useI18n();
  const rows: { label: string; value: string | null; mono?: boolean }[] = [
    { label: t("doctorForm.name"), value: account.name },
    { label: t("doctorForm.specialization"), value: account.specialization },
    { label: t("doctorForm.qualification"), value: account.qualification },
    { label: t("doctorForm.registration"), value: account.registration_identifier, mono: true },
    { label: t("doctorForm.clinicName"), value: account.clinic_name },
    { label: t("doctorForm.phone"), value: account.phone },
    { label: t("doctorForm.clinicAddress"), value: account.clinic_address },
    {
      label: t("doctorForm.languages"),
      value: account.languages.map((code) => languageInfo(code)?.englishName ?? code).join(", "),
    },
  ];
  return (
    <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
      {rows.map((row) => (
        <div key={row.label} className="min-w-0">
          <dt className="text-small text-muted">{row.label}</dt>
          <dd className={cn("mt-0.5 break-words", row.value ? "text-ink" : "text-subtle", row.mono && "font-mono")}>
            {row.value || t("application.notGiven")}
          </dd>
        </div>
      ))}
    </dl>
  );
}
