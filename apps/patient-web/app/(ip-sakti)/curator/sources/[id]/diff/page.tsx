"use client";

import { useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import { Card, ErrorState, PageHeader, SkeletonCard } from "@carebridge/ui";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeftIcon } from "@/components/icons";
import { DiffView } from "@/components/sakti/corpus/DiffView";

/** A source set beside the last approved source of the same instrument. */
export default function SourceDiffPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useI18n();
  const source = useQuery((a) => a.corpus.source(id), [id]);
  const diff = useQuery((a) => a.corpus.sourceDiff(id), [id]);

  return (
    <>
      <PageHeader
        back={
          <Link href={`/curator/sources/${id}`} className="inline-flex items-center gap-1.5 font-medium text-brand-strong hover:underline">
            <ArrowLeftIcon aria-hidden />
            {source.data?.title ?? t("corpus.version.source")}
          </Link>
        }
        title={t("corpus.diff.title")}
        description={source.data ? `${source.data.instrument.title} · ${source.data.authority_name}` : undefined}
      />
      <Card>
        {diff.error && !diff.data ? (
          <ErrorState error={diff.error} onRetry={diff.reload} />
        ) : !diff.data ? (
          <SkeletonCard />
        ) : (
          <DiffView diff={diff.data} noBaseline={t("corpus.diff.noBaseline")} />
        )}
      </Card>
    </>
  );
}
