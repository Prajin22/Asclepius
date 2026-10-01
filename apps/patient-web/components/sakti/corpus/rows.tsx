"use client";

import { useI18n } from "@carebridge/i18n";
import type { CorpusSourceSummary, ProvisionVersionSummary } from "@carebridge/shared-types";
import Link from "next/link";
import type { ReactNode } from "react";
import { IngestionBadge, LaneBadge, ReviewBadge, pageRange } from "./labels";

/** One source document in a list: what it is, where it is from, where it stands. */
export function SourceRow({ source, children }: { source: CorpusSourceSummary; children?: ReactNode }) {
  const { t, formatDate } = useI18n();
  return (
    <div className="flex flex-col gap-2 py-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <Link href={`/curator/sources/${source.id}`} className="font-semibold text-brand-strong hover:underline">
            {source.title}
          </Link>
          <p className="text-small text-muted">
            <Link href={`/curator/instruments/${source.instrument.id}`} className="hover:underline">
              {source.instrument.title}
            </Link>{" "}
            · {t(`corpus.instrumentType.${source.instrument.instrument_type}`)}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <LaneBadge lane={source.lane} />
          <IngestionBadge state={source.ingestion_state} />
          <ReviewBadge state={source.review_state} />
        </div>
      </div>
      <p className="flex flex-wrap gap-x-3 gap-y-1 text-small text-muted">
        <span>{source.authority_name}</span>
        <span>{t(`corpus.documentType.${source.document_type}`)}</span>
        {source.source_date ? <span>{t("corpus.list.dated", { date: formatDate(source.source_date) })}</span> : null}
        <span>{t("corpus.list.retrieved", { date: formatDate(source.retrieved_on) })}</span>
        {source.page_count ? <span>{t("corpus.list.pages", { count: source.page_count })}</span> : null}
        <span>{t(`corpus.terms.${source.terms_status}`)}</span>
      </p>
      {children}
    </div>
  );
}

/** One provision version in a list. */
export function VersionRow({ version, children }: { version: ProvisionVersionSummary; children?: ReactNode }) {
  const { t, formatDate } = useI18n();
  const range =
    version.valid_from || version.valid_to
      ? t("corpus.version.validityRange", {
          from: version.valid_from ? formatDate(version.valid_from) : t("corpus.version.notRecorded"),
          to: version.valid_to ? formatDate(version.valid_to) : t("corpus.version.notRecorded"),
        })
      : null;
  return (
    <div className="flex flex-col gap-2 py-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <Link href={`/curator/versions/${version.id}`} className="font-semibold text-brand-strong hover:underline">
            {t("corpus.version.title", { locator: version.provision.locator, number: version.version_number })}
          </Link>
          <p className="text-small text-muted">
            {version.instrument.title} · {t(`corpus.locatorType.${version.provision.locator_type}`)}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <LaneBadge lane={version.lane} />
          <ReviewBadge state={version.review_state} />
        </div>
      </div>
      <p className="flex flex-wrap gap-x-3 gap-y-1 text-small text-muted">
        <span>{pageRange(t, version.page_start, version.page_end)}</span>
        {range ? <span>{range}</span> : null}
        {version.ocr_derived ? <span>{t("corpus.method.ocr")}</span> : null}
        {version.latest_status ? (
          <span>{t("corpus.version.latest", { status: t(`corpus.status.${version.latest_status}`) })}</span>
        ) : null}
      </p>
      {children}
    </div>
  );
}
