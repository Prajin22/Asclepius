"use client";

import { useApi, useAuth, useQuery } from "@carebridge/api-client/react";
import { errorMessage, useI18n } from "@carebridge/i18n";
import { SEX_VALUES, type LanguageCode, type PatientProfile, type Sex } from "@carebridge/shared-types";
import { Alert, Button, Card, CardHeader, Checkbox, ErrorState, Field, LoadingState, PageHeader, Select, TextArea, TextInput } from "@carebridge/ui";
import { useEffect, useState, type FormEvent } from "react";
import { LanguageSelect } from "@/components/LanguageSelect";

type FormState = {
  display_name: string;
  date_of_birth: string;
  sex: Sex;
  phone: string;
  preferred_language: LanguageCode | "";
  emergency_contact_name: string;
  emergency_contact_phone: string;
  emergency_notes: string;
};

function toForm(p: PatientProfile): FormState {
  return {
    display_name: p.display_name,
    date_of_birth: p.date_of_birth ?? "",
    sex: p.sex,
    phone: p.phone ?? "",
    preferred_language: p.preferred_language,
    emergency_contact_name: p.emergency_contact_name ?? "",
    emergency_contact_phone: p.emergency_contact_phone ?? "",
    emergency_notes: p.emergency_notes ?? "",
  };
}

export default function ProfilePage() {
  const api = useApi();
  const { session } = useAuth();
  const { t } = useI18n();
  const q = useQuery((a) => a.patient.profile());
  const [form, setForm] = useState<FormState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (q.data && !form) setForm(toForm(q.data));
  }, [q.data, form]);

  if (q.error && !q.data) return <ErrorState error={q.error} onRetry={q.reload} />;
  if (!q.data || !form) return <LoadingState />;

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setSaved(false);
    setForm((f) => (f ? { ...f, [key]: value } : f));
  };

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!form || !form.preferred_language) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await api.patient.updateProfile({
        display_name: form.display_name.trim(),
        date_of_birth: form.date_of_birth || null,
        sex: form.sex,
        phone: form.phone.trim() || null,
        preferred_language: form.preferred_language,
        emergency_contact_name: form.emergency_contact_name.trim() || null,
        emergency_contact_phone: form.emergency_contact_phone.trim() || null,
        emergency_notes: form.emergency_notes.trim() || null,
      });
      q.setData(updated);
      setForm(toForm(updated));
      setSaved(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title={t("profile.title")} description={t("profile.subtitle")} />
      <form onSubmit={submit} className="flex max-w-3xl flex-col gap-5">
        <Card>
          <CardHeader
            title={t("profile.personal")}
            description={q.data.age !== null ? t("profile.age", { age: q.data.age }) : undefined}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("profile.displayName")} className="sm:col-span-2">
              {(p) => (
                <TextInput
                  {...p}
                  required
                  maxLength={120}
                  autoComplete="name"
                  value={form.display_name}
                  onChange={(e) => set("display_name", e.target.value)}
                />
              )}
            </Field>
            <Field label={t("profile.dob")}>
              {(p) => (
                <TextInput
                  {...p}
                  type="date"
                  value={form.date_of_birth}
                  onChange={(e) => set("date_of_birth", e.target.value)}
                />
              )}
            </Field>
            <Field label={t("profile.sex")}>
              {(p) => (
                <Select {...p} value={form.sex} onChange={(e) => set("sex", e.target.value as Sex)}>
                  {SEX_VALUES.map((s) => (
                    <option key={s} value={s}>
                      {t(`sex.${s}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t("profile.phone")}>
              {(p) => (
                <TextInput
                  {...p}
                  type="tel"
                  autoComplete="tel"
                  maxLength={32}
                  value={form.phone}
                  onChange={(e) => set("phone", e.target.value)}
                />
              )}
            </Field>
            <Field label={t("profile.preferredLanguage")} hint={t("profile.preferredLanguageHint")}>
              {(p) => (
                <LanguageSelect {...p} value={form.preferred_language} onChange={(v) => set("preferred_language", v)} />
              )}
            </Field>
          </div>
        </Card>

        <Card>
          <CardHeader title={t("profile.emergency")} description={t("profile.emergencyPrivate")} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("profile.emergencyName")}>
              {(p) => (
                <TextInput
                  {...p}
                  maxLength={120}
                  value={form.emergency_contact_name}
                  onChange={(e) => set("emergency_contact_name", e.target.value)}
                />
              )}
            </Field>
            <Field label={t("profile.emergencyPhone")}>
              {(p) => (
                <TextInput
                  {...p}
                  type="tel"
                  maxLength={32}
                  value={form.emergency_contact_phone}
                  onChange={(e) => set("emergency_contact_phone", e.target.value)}
                />
              )}
            </Field>
            <Field label={t("profile.emergencyNotes")} className="sm:col-span-2">
              {(p) => (
                <TextArea
                  {...p}
                  rows={2}
                  maxLength={2000}
                  value={form.emergency_notes}
                  onChange={(e) => set("emergency_notes", e.target.value)}
                />
              )}
            </Field>
          </div>
        </Card>

        <Card>
          <CardHeader title={t("ai.consentTitle")} description={t("ai.subtitle")} />
          <p className="mb-3 text-muted">{t("ai.consentBody")}</p>
          <p className="mb-3 text-sm text-muted">{t("ai.consentExternalNote")}</p>
          <Checkbox
            label={q.data.ai_processing_consent ? t("ai.consentOn") : t("ai.consentOff")}
            description={t("ai.notDiagnosis")}
            checked={q.data.ai_processing_consent}
            onChange={async (granted) => {
              setSaved(false);
              q.setData(await api.ai.setConsent(granted));
            }}
          />
        </Card>

        <Card>
          <CardHeader title={t("profile.account")} />
          <p className="text-sm text-muted">{t("profile.email")}</p>
          <p className="font-medium">{session?.user.email}</p>
        </Card>

        {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
        {saved ? <Alert tone="success">{t("profile.saved")}</Alert> : null}
        <div>
          <Button type="submit" size="lg" disabled={busy}>
            {busy ? t("actions.saving") : t("actions.save")}
          </Button>
        </div>
      </form>
    </>
  );
}
