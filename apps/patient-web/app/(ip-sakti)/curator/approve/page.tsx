"use client";

import { useApi, useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import { Alert, Card, EmptyState, ErrorState, PageHeader, SkeletonCard } from "@carebridge/ui";
import Link from "next/link";
import { useState } from "react";
import { ReviewActions } from "@/components/sakti/corpus/ReviewActions";
import { SourceRow, VersionRow } from "@/components/sakti/corpus/rows";

/**
 * Everything submitted for review. Each approval names the checksum shown
 * beside it; a version waits until its source document is approved.
 */
export default function ApprovePage() {
  const api = useApi();
  const { t } = useI18n();
  const q = useQuery((a) => a.corpus.reviewQueue());
  const [notice, setNotice] = useState<string | null>(null);

  async function decided(run: () => Promise<unknown>, approved: boolean) {
    await run();
    setNotice(t(approved ? "corpus.review.approvedNotice" : "corpus.review.rejectedNotice"));
    q.reload();
  }

  return (
    <>
      <PageHeader title={t("pages.approve.title")} description={t("pages.approve.description")} />
      {notice ? (
        <Alert tone="success" className="mb-4">
          {notice}
        </Alert>
      ) : null}
      {q.error && !q.data ? (
        <ErrorState error={q.error} onRetry={q.reload} />
      ) : !q.data ? (
        <SkeletonCard />
      ) : q.data.sources.length + q.data.versions.length === 0 ? (
        <EmptyState>{t("corpus.queue.emptyReview")}</EmptyState>
      ) : (
        <div className="flex flex-col gap-8">
          {q.data.sources.length ? (
            <section aria-labelledby="review-sources" className="flex flex-col gap-3">
              <h2 id="review-sources" className="text-subheading text-ink">
                {t("corpus.queue.sources")}
              </h2>
              {q.data.sources.map((source) => (
                <Card key={source.id} padding="none" className="px-5 pb-5 sm:px-6">
                  <SourceRow source={source}>
                    <Link href={`/curator/sources/${source.id}`} className="text-small font-semibold text-brand-strong hover:underline">
                      {t("corpus.queue.inspect")}
                    </Link>
                  </SourceRow>
                  <ReviewActions
                    checksum={source.sha256}
                    needsAcknowledgment={source.ingestion_state === "needs_review"}
                    onApprove={(ack) => decided(() => api.corpus.approveSource(source.id, source.sha256, ack), true)}
                    onReject={(reason) => decided(() => api.corpus.rejectSource(source.id, reason), false)}
                  />
                </Card>
              ))}
            </section>
          ) : null}
          {q.data.versions.length ? (
            <section aria-labelledby="review-versions" className="flex flex-col gap-3">
              <h2 id="review-versions" className="text-subheading text-ink">
                {t("corpus.queue.versions")}
              </h2>
              {q.data.versions.map((version) => (
                <Card key={version.id} padding="none" className="px-5 pb-5 sm:px-6">
                  <VersionRow version={version}>
                    <Link href={`/curator/versions/${version.id}`} className="text-small font-semibold text-brand-strong hover:underline">
                      {t("corpus.queue.inspect")}
                    </Link>
                  </VersionRow>
                  <ReviewActions
                    checksum={version.text_sha256}
                    needsAcknowledgment={version.ocr_derived}
                    blocked={version.source_review_state === "approved" ? undefined : t("corpus.review.needsSource")}
                    onApprove={(ack) => decided(() => api.corpus.approveVersion(version.id, version.text_sha256, ack), true)}
                    onReject={(reason) => decided(() => api.corpus.rejectVersion(version.id, reason), false)}
                  />
                </Card>
              ))}
            </section>
          ) : null}
        </div>
      )}
    </>
  );
}
