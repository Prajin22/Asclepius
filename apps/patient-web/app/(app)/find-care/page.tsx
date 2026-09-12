"use client";

import { useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import { LANGUAGES, languageInfo, type LanguageCode } from "@carebridge/shared-types";
import { Alert, Badge, Button, EmptyState, ErrorState, Field, LoadingState, PageHeader, Select, TextInput, buttonClasses } from "@carebridge/ui";
import Link from "next/link";
import { useMemo, useState, type FormEvent } from "react";

interface Filters {
  q: string;
  specialization: string;
  language: LanguageCode | "";
}

export default function FindCarePage() {
  const { t } = useI18n();
  const [draft, setDraft] = useState("");
  const [filters, setFilters] = useState<Filters>({ q: "", specialization: "", language: "" });
  const all = useQuery((a) => a.directory.search({}));
  const results = useQuery((a) => a.directory.search(filters), [filters.q, filters.specialization, filters.language]);

  const specializations = useMemo(
    () => [...new Set((all.data ?? []).map((d) => d.specialization))].sort(),
    [all.data],
  );

  function submit(e: FormEvent) {
    e.preventDefault();
    setFilters((f) => ({ ...f, q: draft.trim() }));
  }

  return (
    <>
      <PageHeader title={t("findCare.title")} description={t("findCare.subtitle")} />

      <form
        onSubmit={submit}
        role="search"
        className="mb-5 grid gap-4 rounded-xl border border-line bg-surface p-4 sm:p-5 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_auto] md:items-end"
      >
        <Field label={t("findCare.search")}>
          {(p) => (
            <TextInput
              {...p}
              type="search"
              placeholder={t("findCare.searchPlaceholder")}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
            />
          )}
        </Field>
        <Field label={t("findCare.specialization")}>
          {(p) => (
            <Select
              {...p}
              value={filters.specialization}
              onChange={(e) => setFilters((f) => ({ ...f, specialization: e.target.value }))}
            >
              <option value="">{t("findCare.anySpecialization")}</option>
              {specializations.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label={t("findCare.language")}>
          {(p) => (
            <Select
              {...p}
              value={filters.language}
              onChange={(e) => setFilters((f) => ({ ...f, language: e.target.value as LanguageCode | "" }))}
            >
              <option value="">{t("findCare.anyLanguage")}</option>
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code} lang={l.code}>
                  {l.nativeName}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Button type="submit">{t("findCare.search")}</Button>
      </form>

      <Alert tone="info" className="mb-5">
        {t("findCare.demoNotice")}
      </Alert>

      {results.error && !results.data ? (
        <ErrorState error={results.error} onRetry={results.reload} />
      ) : !results.data ? (
        <LoadingState />
      ) : results.data.length === 0 ? (
        <EmptyState>{t("findCare.noResults")}</EmptyState>
      ) : (
        <>
          <p className="mb-3 text-sm text-muted" role="status">
            {t("findCare.resultCount", { count: results.data.length })}
          </p>
          <ul className="grid gap-4 md:grid-cols-2">
            {results.data.map((d) => (
              <li key={d.id} className="flex flex-col rounded-xl border border-line bg-surface p-5">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-lg font-semibold">{d.name}</p>
                    <p className="font-medium text-brand-strong">{d.specialization}</p>
                    <p className="text-sm text-muted">{d.qualification}</p>
                  </div>
                  {!d.is_accepting_consultations ? <Badge tone="warning">{t("findCare.notAccepting")}</Badge> : null}
                </div>
                {d.clinic_name ? <p className="mt-3">{d.clinic_name}</p> : null}
                {d.clinic_address ? <p className="text-sm text-muted">{d.clinic_address}</p> : null}
                <p className="mt-2 text-sm">
                  {t("findCare.speaks", {
                    languages: d.languages.map((c) => languageInfo(c)?.nativeName ?? c).join(" · "),
                  })}
                </p>
                <p className="mt-1 text-xs text-subtle">{t("prescription.registration", { id: d.registration_identifier })}</p>
                <div className="mt-4 flex-1" />
                {d.is_accepting_consultations ? (
                  <Link href={`/find-care/${d.id}`} className={buttonClasses("primary", "md", "w-full")}>
                    {t("findCare.request")}
                  </Link>
                ) : null}
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}
