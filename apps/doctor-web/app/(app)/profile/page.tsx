"use client";

import { useApi, useAuth, useQuery } from "@carebridge/api-client/react";
import { errorMessage, useI18n } from "@carebridge/i18n";
import { LANGUAGES, type DoctorPublic, type LanguageCode } from "@carebridge/shared-types";
import { Alert, Button, Card, CardHeader, Checkbox, ErrorState, Field, LoadingState, PageHeader, TextArea, TextInput } from "@carebridge/ui";
import { useEffect, useState, type FormEvent } from "react";

type FormState = {
  name: string;
  specialization: string;
  qualification: string;
  clinic_name: string;
  clinic_address: string;
  phone: string;
  languages: LanguageCode[];
  is_accepting_consultations: boolean;
};

const toForm = (d: DoctorPublic): FormState => ({
  name: d.name,
  specialization: d.specialization,
  qualification: d.qualification,
  clinic_name: d.clinic_name ?? "",
  clinic_address: d.clinic_address ?? "",
  phone: d.phone ?? "",
  languages: d.languages,
  is_accepting_consultations: d.is_accepting_consultations,
});

export default function DoctorProfilePage() {
  const api = useApi();
  const { session } = useAuth();
  const { t } = useI18n();
  const q = useQuery((a) => a.doctor.profile());
  const [form, setForm] = useState<FormState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (q.data && !form) setForm(toForm(q.data));
  }, [q.data, form]);

  if (q.error && !q.data) return <ErrorState error={q.error} onRetry={q.reload} />;
  if (!q.data || !form) return <LoadingState />;

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => {
    setSaved(false);
    setForm((f) => (f ? { ...f, [k]: v } : f));
  };

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!form) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await api.doctor.updateProfile({
        name: form.name.trim(),
        specialization: form.specialization.trim(),
        qualification: form.qualification.trim(),
        clinic_name: form.clinic_name.trim() || null,
        clinic_address: form.clinic_address.trim() || null,
        phone: form.phone.trim() || null,
        languages: form.languages,
        is_accepting_consultations: form.is_accepting_consultations,
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

  const text = (key: keyof FormState, label: string, max: number) => (
    <Field label={label}>
      {(p) => (
        <TextInput {...p} maxLength={max} value={form[key] as string} onChange={(e) => set(key, e.target.value as never)} />
      )}
    </Field>
  );

  return (
    <>
      <PageHeader title={t("profile.title")} description={t("profile.subtitle")} />
      <form onSubmit={submit} className="flex max-w-3xl flex-col gap-5">
        <Card>
          <div className="grid gap-4 sm:grid-cols-2">
            {text("name", t("profile.name"), 120)}
            {text("specialization", t("profile.specialization"), 120)}
            {text("qualification", t("profile.qualification"), 200)}
            <div>
              <p className="text-sm font-semibold">{t("profile.registration")}</p>
              <p className="mt-2 font-mono">{q.data.registration_identifier}</p>
              <p className="mt-1 text-sm text-muted">{t("profile.registrationHint")}</p>
            </div>
            {text("clinic_name", t("profile.clinicName"), 200)}
            {text("phone", t("profile.phone"), 32)}
            <Field label={t("profile.clinicAddress")} className="sm:col-span-2">
              {(p) => (
                <TextArea {...p} rows={2} maxLength={1000} value={form.clinic_address} onChange={(e) => set("clinic_address", e.target.value)} />
              )}
            </Field>
          </div>
        </Card>
        <Card>
          <CardHeader title={t("profile.languages")} />
          <div className="grid gap-2 sm:grid-cols-3">
            {LANGUAGES.map((l) => (
              <Checkbox
                key={l.code}
                label={
                  <>
                    {l.englishName} <span lang={l.code} className="text-muted">({l.nativeName})</span>
                  </>
                }
                checked={form.languages.includes(l.code)}
                onChange={(checked) =>
                  set("languages", checked ? [...form.languages, l.code] : form.languages.filter((c) => c !== l.code))
                }
              />
            ))}
          </div>
        </Card>
        <Card>
          <Checkbox
            label={t("profile.accepting")}
            description={session?.user.email}
            checked={form.is_accepting_consultations}
            onChange={(v) => set("is_accepting_consultations", v)}
          />
        </Card>
        {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
        {saved ? <Alert tone="success">{t("profile.saved")}</Alert> : null}
        <div>
          <Button type="submit" size="lg" disabled={busy || form.languages.length === 0}>
            {busy ? t("actions.saving") : t("actions.save")}
          </Button>
        </div>
      </form>
    </>
  );
}
