"use client";

import { useApi, useQuery } from "@carebridge/api-client/react";
import { errorMessage, useI18n } from "@carebridge/i18n";
import { SHARE_CATEGORIES, languageInfo, type LanguageCode } from "@carebridge/shared-types";
import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  CardHeader,
  ErrorState,
  Field,
  PageHeader,
  SkeletonCard,
  TextArea,
  buttonClasses,
} from "@carebridge/ui";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ArrowLeftIcon } from "@/components/icons";
import { ShareSelector } from "@/components/ShareSelector";
import { buildShareItems, defaultSelection, emptySelection, toShareSelection, type SelectionState } from "@/lib/sharing";

export default function RequestConsultationPage() {
  const { doctorId } = useParams<{ doctorId: string }>();
  const api = useApi();
  const router = useRouter();
  const { t, formatDate, locale } = useI18n();
  const q = useQuery(
    async (a) => {
      const [doctor, records, documents, consultations, prescriptions] = await Promise.all([
        a.directory.get(doctorId),
        a.patient.records(),
        a.patient.documents(),
        a.patient.consultations(),
        a.patient.prescriptions(),
      ]);
      return { doctor, records, documents, consultations, prescriptions };
    },
    [doctorId],
  );
  const [selection, setSelection] = useState<SelectionState>(emptySelection);
  const [initialised, setInitialised] = useState(false);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (q.data && !initialised) {
      setSelection(defaultSelection(q.data));
      setInitialised(true);
    }
  }, [q.data, initialised]);

  const items = useMemo(() => (q.data ? buildShareItems(q.data, t, formatDate) : null), [q.data, t, formatDate]);

  const back = (
    <Link href="/find-care" className="inline-flex items-center gap-1.5 font-medium text-brand hover:underline">
      <ArrowLeftIcon />
      {t("findCare.title")}
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
  if (!q.data || !items) return <SkeletonCard />;
  const { doctor } = q.data;
  const selectedCategories = SHARE_CATEGORIES.filter((c) => selection[c].length > 0);

  async function submit() {
    setBusy(true);
    setError(null);
    const note = message.trim();
    try {
      const c = await api.patient.requestConsultation({
        doctor_id: doctor.id,
        share: toShareSelection(selection),
        request_message: note || null,
        request_language: note ? (locale as LanguageCode) : null,
      });
      router.push(`/consultations/${c.id}`);
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader eyebrow={back} title={t("request.title")} />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="flex min-w-0 flex-col gap-5">
          <Card>
            <CardHeader title={t("request.shareTitle")} description={t("request.shareSubtitle", { name: doctor.name })} />
            <Alert tone="info" className="mb-4">
              {t("request.alwaysShared")}
            </Alert>
            {items.current_problem.length === 0 ? (
              <Alert tone="warning" className="mb-4" title={t("request.noProblem")}>
                <Link href="/health/current-problem" className="font-semibold underline">
                  {t("request.describeNow")}
                </Link>
              </Alert>
            ) : null}
            <ShareSelector items={items} value={selection} onChange={setSelection} />
          </Card>

          <Card>
            <Field label={t("request.messageLabel")} hint={t("request.messageHint")}>
              {(p) => (
                <TextArea
                  {...p}
                  rows={3}
                  maxLength={2000}
                  lang={locale}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                />
              )}
            </Field>
          </Card>
        </div>

        <div className="flex min-w-0 flex-col gap-5">
          <Card>
            <div className="flex items-start gap-3.5">
              <Avatar name={doctor.name} size="lg" />
              <div className="min-w-0">
                <p className="text-subheading text-ink">{doctor.name}</p>
                <p className="font-medium text-brand-strong">{doctor.specialization}</p>
                <p className="text-small text-muted">{doctor.qualification}</p>
              </div>
            </div>
            {doctor.clinic_name ? <p className="mt-3 text-body">{doctor.clinic_name}</p> : null}
            <p className="mt-2.5 flex flex-wrap gap-1.5">
              {doctor.languages.map((code) => (
                <Badge key={code} tone="neutral">
                  <span lang={code}>{languageInfo(code)?.nativeName ?? code}</span>
                </Badge>
              ))}
            </p>
          </Card>

          {/* The decision to share sits within reach on a phone, and beside the choices on a desktop. */}
          <Card className="max-lg:sticky max-lg:bottom-20 max-lg:z-20 max-lg:shadow-lg lg:sticky lg:top-24">
            <CardHeader title={t("request.reviewTitle")} />
            {selectedCategories.length === 0 ? (
              <p className="text-muted">{t("request.nothingSelected")}</p>
            ) : (
              <ul className="flex flex-col gap-1.5">
                {selectedCategories.map((cat) => (
                  <li key={cat} className="flex items-center justify-between gap-3">
                    <span>{t(`shareCategories.${cat}`)}</span>
                    <span className="text-sm text-muted">{t("request.selected", { count: selection[cat].length })}</span>
                  </li>
                ))}
              </ul>
            )}
            {error ? (
              <Alert tone="error" className="mt-4">
                {errorMessage(t, error)}
              </Alert>
            ) : null}
            <Button size="lg" className="mt-5 w-full" disabled={busy} onClick={submit}>
              {busy ? t("request.submitting") : t("request.submit")}
            </Button>
            <Link href="/find-care" className={buttonClasses("ghost", "md", "mt-2 w-full")}>
              {t("actions.cancel")}
            </Link>
          </Card>
        </div>
      </div>
    </>
  );
}
