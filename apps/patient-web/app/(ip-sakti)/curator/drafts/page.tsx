"use client";

import { useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import { Card, ErrorState, PageHeader, SkeletonCard } from "@carebridge/ui";
import Link from "next/link";
import { DraftIcon } from "@/components/icons";
import { SourceRow, VersionRow } from "@/components/sakti/corpus/rows";
import { EmptyPanel } from "@/components/sakti/ui";

/** Work in progress, each piece one step from its comparison with what is approved. */
export default function DraftsPage() {
  const { t } = useI18n();
  const q = useQuery((a) => a.corpus.drafts());

  return (
    <>
      <PageHeader title={t("pages.drafts.title")} description={t("pages.drafts.description")} />
      {q.error && !q.data ? (
        <ErrorState error={q.error} onRetry={q.reload} />
      ) : !q.data ? (
        <SkeletonCard />
      ) : q.data.sources.length + q.data.versions.length === 0 ? (
        <EmptyPanel icon={DraftIcon} title={t("corpus.queue.emptyDrafts")}>
          {t("corpus.queue.emptyDraftsBody")}
        </EmptyPanel>
      ) : (
        <div className="flex flex-col gap-8">
          {q.data.sources.length ? (
            <section aria-labelledby="draft-sources" className="flex flex-col gap-3">
              <h2 id="draft-sources" className="text-subheading text-ink">
                {t("corpus.queue.sources")}
              </h2>
              <Card padding="none" className="px-5 sm:px-6">
                <ul className="divide-y divide-line">
                  {q.data.sources.map((source) => (
                    <li key={source.id}>
                      <SourceRow source={source}>
                        {source.ingestion_state === "parsed" || source.ingestion_state === "needs_review" ? (
                          <Link href={`/curator/sources/${source.id}/diff`} className="text-small font-semibold text-brand-strong hover:underline">
                            {t("corpus.queue.compare")}
                          </Link>
                        ) : null}
                      </SourceRow>
                    </li>
                  ))}
                </ul>
              </Card>
            </section>
          ) : null}
          {q.data.versions.length ? (
            <section aria-labelledby="draft-versions" className="flex flex-col gap-3">
              <h2 id="draft-versions" className="text-subheading text-ink">
                {t("corpus.queue.versions")}
              </h2>
              <Card padding="none" className="px-5 sm:px-6">
                <ul className="divide-y divide-line">
                  {q.data.versions.map((version) => (
                    <li key={version.id}>
                      <VersionRow version={version}>
                        <Link href={`/curator/versions/${version.id}`} className="text-small font-semibold text-brand-strong hover:underline">
                          {t("corpus.queue.compare")}
                        </Link>
                      </VersionRow>
                    </li>
                  ))}
                </ul>
              </Card>
            </section>
          ) : null}
        </div>
      )}
    </>
  );
}
