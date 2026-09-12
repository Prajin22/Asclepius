"use client";

import { useApi, useQuery } from "@carebridge/api-client/react";
import { errorMessage, useI18n } from "@carebridge/i18n";
import type { LanguageCode, MedicalRecord } from "@carebridge/shared-types";
import {
  Alert,
  Button,
  Card,
  CardHeader,
  Field,
  LanguageTag,
  PageHeader,
  ProvenanceBlock,
  TextArea,
  buttonClasses,
} from "@carebridge/ui";
import { ArrowRight } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { AIAssistPanel } from "@/components/AIAssistPanel";
import { LanguageSelect } from "@/components/LanguageSelect";

export default function CurrentProblemPage() {
  const api = useApi();
  const { t, formatDate, locale } = useI18n();
  const [text, setText] = useState("");
  const [language, setLanguage] = useState<LanguageCode | "">(locale as LanguageCode);
  const [touchedLanguage, setTouchedLanguage] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState<MedicalRecord | null>(null);
  const previous = useQuery((a) => a.patient.records("current_problem"));
  const profile = useQuery((a) => a.patient.profile());
  // AI assistance applies to the newest description (just saved, or the last one).
  const target = saved ?? previous.data?.[0] ?? null;
  const aiState = useQuery(async (a) => (target ? a.ai.forRecord(target.id) : null), [target?.id]);

  // Follow the UI language until the patient picks a writing language explicitly.
  useEffect(() => {
    if (!touchedLanguage) setLanguage(locale as LanguageCode);
  }, [locale, touchedLanguage]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!text.trim() || !language) return;
    setBusy(true);
    setError(null);
    try {
      const record = await api.patient.createCurrentProblem(text.trim(), language);
      setSaved(record);
      setText("");
      await previous.reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const earlier = (previous.data ?? []).filter((r) => r.id !== target?.id);

  return (
    <>
      <PageHeader title={t("problem.title")} description={t("problem.subtitle")} />

      <div className="flex flex-col gap-5">
        <Card className="mx-auto w-full max-w-3xl" aria-labelledby="describe-heading">
          <CardHeader id="describe-heading" title={t("problem.textLabel")} description={t("problem.textHint")} />
          <form onSubmit={submit} className="flex flex-col gap-4">
            <Field label={t("problem.textLabel")} className="[&>label]:sr-only">
              {(p) => (
                <TextArea
                  {...p}
                  rows={7}
                  required
                  maxLength={10000}
                  lang={language || undefined}
                  className="text-body-lg leading-relaxed"
                  placeholder={t("problem.placeholder")}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                />
              )}
            </Field>
            <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
              <Field label={t("problem.languageLabel")}>
                {(p) => (
                  <LanguageSelect
                    {...p}
                    value={language}
                    onChange={(v) => {
                      setTouchedLanguage(true);
                      setLanguage(v);
                    }}
                  />
                )}
              </Field>
              <Button type="submit" size="lg" loading={busy} disabled={!text.trim()} className="max-sm:w-full">
                {busy ? t("actions.saving") : t("problem.submit")}
              </Button>
            </div>
            {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
            {saved ? (
              <Alert tone="success" title={t("problem.saved")}>
                <Link href="/find-care" className="mt-1 inline-flex items-center gap-1.5 font-semibold underline">
                  {t("problem.nextFindDoctor")}
                  <ArrowRight size={15} aria-hidden />
                </Link>
              </Alert>
            ) : null}
          </form>
        </Card>

        {target ? (
          <div className="mx-auto w-full max-w-3xl">
            <AIAssistPanel
              originalText={target.content}
              hasConsent={profile.data?.ai_processing_consent ?? false}
              result={aiState.data ?? null}
              onGrantConsent={async () => {
                await api.ai.setConsent(true);
                await profile.reload();
              }}
              onProcess={() => api.ai.process(target.id)}
              onReviewFact={(factId, action) => api.ai.reviewFact(factId, action)}
            />
          </div>
        ) : null}

        {earlier.length > 0 ? (
          <Card className="mx-auto w-full max-w-3xl" aria-labelledby="earlier-heading">
            <CardHeader id="earlier-heading" title={t("problem.previous")} />
            <ul className="flex flex-col gap-3">
              {earlier.map((r) => (
                <li key={r.id}>
                  <ProvenanceBlock
                    kind="original"
                    lang={r.source_language}
                    meta={
                      <span className="flex flex-wrap items-center gap-2">
                        <LanguageTag code={r.source_language} />
                        <span>{formatDate(r.created_at)}</span>
                        <span>· {t(`recordStatus.${r.status}`)}</span>
                      </span>
                    }
                  >
                    <p className="whitespace-pre-line">{r.content}</p>
                  </ProvenanceBlock>
                </li>
              ))}
            </ul>
            <Link href="/find-care" className={buttonClasses("secondary", "md", "mt-4 w-full sm:w-auto")}>
              {t("problem.nextFindDoctor")}
            </Link>
          </Card>
        ) : null}
      </div>
    </>
  );
}
