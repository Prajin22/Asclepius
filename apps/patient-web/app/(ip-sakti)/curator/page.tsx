"use client";

import { useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import type { CorpusLane } from "@carebridge/shared-types";
import { Alert, Card, EmptyState, ErrorState, PageHeader, SegmentedTabs, Skeleton, SkeletonCard, buttonClasses } from "@carebridge/ui";
import { Books, HourglassMedium, PencilSimpleLine, SealCheck, XCircle } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useState } from "react";
import { CorpusIcon, UploadIcon } from "@/components/icons";
import { ClassifierReferenceStatus } from "@/components/sakti/corpus/ClassifierReferences";
import { LaneBadge } from "@/components/sakti/corpus/labels";
import { SourceRow } from "@/components/sakti/corpus/rows";
import { EmptyPanel, StatTile } from "@/components/sakti/ui";

type LaneFilter = "all" | CorpusLane;
const FILTERS: LaneFilter[] = ["all", "india", "international"];

/** The corpus: where it stands, then every source document and instrument, by lane. */
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
      <section aria-labelledby="corpus-stats" className="mb-6">
        <h2 id="corpus-stats" className="sr-only">
          {t("corpus.stats.title")}
        </h2>
        {sources.data ? (
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
            {(
              [
                ["total", Books, "brand"],
                ["draft", PencilSimpleLine, "neutral"],
                ["under_review", HourglassMedium, "info"],
                ["approved", SealCheck, "success"],
                ["rejected", XCircle, "danger"],
              ] as const
            ).map(([key, icon, tone]) => (
              <li key={key} className={key === "total" ? "col-span-2 sm:col-span-1" : undefined}>
                <StatTile
                  label={t(key === "total" ? "corpus.stats.total" : `corpus.reviewState.${key}`)}
                  value={key === "total" ? sources.data!.length : sources.data!.filter((s) => s.review_state === key).length}
                  icon={icon}
                  tone={tone}
                />
              </li>
            ))}
          </ul>
        ) : sources.error ? null : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
            {Array.from({ length: 5 }, (_, i) => (
              <Skeleton key={i} className="h-20 rounded-md" />
            ))}
          </div>
        )}
        <p className="mt-2 text-caption text-subtle">{t(lane === "all" ? "corpus.stats.allLanes" : "corpus.stats.thisLane")}</p>
      </section>

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
        <div className="mt-3 flex flex-col gap-3">
          {sources.error && !sources.data ? (
            <ErrorState error={sources.error} onRetry={sources.reload} />
          ) : !sources.data ? (
            <SkeletonCard />
          ) : sources.data.length === 0 ? (
            <EmptyPanel
              icon={CorpusIcon}
              title={t("corpus.stats.noApproved")}
              action={
                <Link href="/curator/upload" className={buttonClasses("primary", "md")}>
                  {t("corpus.list.upload")}
                </Link>
              }
            >
              {t(lane === "all" ? "corpus.list.empty" : "corpus.list.emptyLane")}
            </EmptyPanel>
          ) : (
            <>
              {sources.data.every((s) => s.review_state !== "approved") ? (
                <Alert tone="info" title={t("corpus.stats.noApproved")}>
                  {t("corpus.stats.noApprovedBody")}
                </Alert>
              ) : null}
              <Card padding="none" className="px-5 sm:px-6">
                <ul className="divide-y divide-line">
                  {sources.data.map((source) => (
                    <li key={source.id}>
                      <SourceRow source={source} />
                    </li>
                  ))}
                </ul>
              </Card>
            </>
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
