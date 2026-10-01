"use client";

import { useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import type { CorpusLane } from "@carebridge/shared-types";
import { Card, EmptyState, ErrorState, PageHeader, SegmentedTabs, SkeletonCard, buttonClasses } from "@carebridge/ui";
import Link from "next/link";
import { useState } from "react";
import { UploadIcon } from "@/components/icons";
import { ClassifierReferenceStatus } from "@/components/sakti/corpus/ClassifierReferences";
import { LaneBadge } from "@/components/sakti/corpus/labels";
import { SourceRow } from "@/components/sakti/corpus/rows";

type LaneFilter = "all" | CorpusLane;
const FILTERS: LaneFilter[] = ["all", "india", "international"];

/** The corpus: every source document and instrument, by lane. */
export default function CorpusPage() {
  const { t } = useI18n();
  const [lane, setLane] = useState<LaneFilter>("all");
  const filter = lane === "all" ? undefined : lane;
  const sources = useQuery((a) => a.corpus.sources({ lane: filter }), [filter]);
  const instruments = useQuery((a) => a.corpus.instruments(filter), [filter]);

  return (
    <>
      <PageHeader
        title={t("pages.corpus.title")}
        description={t("pages.corpus.description")}
        actions={
          <Link href="/curator/upload" className={buttonClasses("primary", "md", "gap-2")}>
            <UploadIcon size={18} aria-hidden />
            {t("corpus.list.upload")}
          </Link>
        }
      />
      <SegmentedTabs
        label={t("corpus.list.filter")}
        value={lane}
        onChange={setLane}
        items={FILTERS.map((value) => ({ value, label: t(value === "all" ? "corpus.lane.all" : `corpus.lane.${value}`) }))}
      />
      <p className="mt-2 text-small text-muted">{t("corpus.lane.hint")}</p>

      <section aria-labelledby="sources-title" className="mt-6">
        <h2 id="sources-title" className="text-subheading text-ink">
          {t("corpus.list.sourcesTitle")}
        </h2>
        <div className="mt-3">
          {sources.error && !sources.data ? (
            <ErrorState error={sources.error} onRetry={sources.reload} />
          ) : !sources.data ? (
            <SkeletonCard />
          ) : sources.data.length === 0 ? (
            <EmptyState>{t(lane === "all" ? "corpus.list.empty" : "corpus.list.emptyLane")}</EmptyState>
          ) : (
            <Card padding="none" className="px-5 sm:px-6">
              <ul className="divide-y divide-line">
                {sources.data.map((source) => (
                  <li key={source.id}>
                    <SourceRow source={source} />
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      </section>

      <section aria-labelledby="classifier-references" className="mt-8">
        <h2 id="classifier-references" className="text-subheading text-ink">
          {t("corpus.classifier.listTitle")}
        </h2>
        <Card className="mt-3">
          <ClassifierReferenceStatus />
        </Card>
      </section>

      <section aria-labelledby="instruments-title" className="mt-8">
        <h2 id="instruments-title" className="text-subheading text-ink">
          {t("corpus.list.instrumentsTitle")}
        </h2>
        <div className="mt-3">
          {instruments.error && !instruments.data ? (
            <ErrorState error={instruments.error} onRetry={instruments.reload} />
          ) : !instruments.data ? (
            <SkeletonCard />
          ) : instruments.data.length === 0 ? (
            <EmptyState>{t("corpus.list.noInstruments")}</EmptyState>
          ) : (
            <ul className="grid gap-3 sm:grid-cols-2">
              {instruments.data.map((instrument) => (
                <li key={instrument.id}>
                  <Card className="h-full">
                    <div className="flex items-start justify-between gap-2">
                      <Link
                        href={`/curator/instruments/${instrument.id}`}
                        className="font-semibold text-brand-strong hover:underline"
                      >
                        {instrument.title}
                      </Link>
                      <LaneBadge lane={instrument.lane} />
                    </div>
                    <p className="mt-1 text-small text-muted">
                      {t(`corpus.instrumentType.${instrument.instrument_type}`)} ·{" "}
                      {t("corpus.instrument.issuedBy", { issuer: instrument.issued_by })}
                    </p>
                  </Card>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </>
  );
}
