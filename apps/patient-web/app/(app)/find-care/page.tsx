"use client";

import { useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import { LANGUAGES, languageInfo, type LanguageCode } from "@carebridge/shared-types";
import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  PageHeader,
  Select,
  SkeletonCard,
  TextInput,
  buttonClasses,
} from "@carebridge/ui";
import { MagnifyingGlass } from "@phosphor-icons/react/dist/ssr";
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

  const specializations = useMemo(() => [...new Set((all.data ?? []).map((d) => d.specialization))].sort(), [all.data]);

  function submit(e: FormEvent) {
    e.preventDefault();
    setFilters((f) => ({ ...f, q: draft.trim() }));
  }

  return (
    <>
      <PageHeader title={t("findCare.title")} description={t("findCare.subtitle")} />

      <Card padding="sm" className="mb-4" as="div">
        <form
          onSubmit={submit}
          role="search"
          className="grid gap-3 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_auto] md:items-end"
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
          <Button type="submit" className="max-md:w-full">
            <MagnifyingGlass size={17} aria-hidden />
            {t("findCare.search")}
          </Button>
        </form>
      </Card>

      <Alert tone="info" className="mb-5">
        {t("findCare.demoNotice")}
      </Alert>

      {results.error && !results.data ? (
        <ErrorState error={results.error} onRetry={results.reload} />
      ) : !results.data ? (
        <div className="grid gap-4 md:grid-cols-2">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : results.data.length === 0 ? (
        <EmptyState title={t("findCare.noResults")}>{t("findCare.noResultsWhy")}</EmptyState>
      ) : (
        <>
          <p className="mb-3 text-small text-muted" role="status">
            {t("findCare.resultCount", { count: results.data.length })}
          </p>
          <ul className="grid gap-4 md:grid-cols-2">
            {results.data.map((d) => (
              <li key={d.id} className="flex flex-col rounded-md border border-line bg-surface p-5">
                <div className="flex items-start gap-3.5">
                  <Avatar name={d.name} size="lg" />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-subheading text-ink">{d.name}</p>
                        <p className="font-medium text-brand-strong">{d.specialization}</p>
                        <p className="text-small text-muted">{d.qualification}</p>
                      </div>
                      {!d.is_accepting_consultations ? (
                        <Badge tone="warning">{t("findCare.notAccepting")}</Badge>
                      ) : null}
                    </div>
                  </div>
                </div>
                {d.clinic_name ? <p className="mt-3.5 text-body">{d.clinic_name}</p> : null}
                {d.clinic_address ? <p className="text-small text-muted">{d.clinic_address}</p> : null}
                <p className="mt-2.5 flex flex-wrap gap-1.5">
                  {d.languages.map((code) => (
                    <Badge key={code} tone="neutral">
                      <span lang={code}>{languageInfo(code)?.nativeName ?? code}</span>
                    </Badge>
                  ))}
                </p>
                <p className="mt-2 text-caption text-subtle">
                  {t("prescription.registration", { id: d.registration_identifier })}
                </p>
                <div className="mt-4 flex-1" />
                {/* Every card offers the same step, so none of them shouts: the choice is which doctor. */}
                {d.is_accepting_consultations ? (
                  <Link href={`/find-care/${d.id}`} className={buttonClasses("secondary", "md", "w-full")}>
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
