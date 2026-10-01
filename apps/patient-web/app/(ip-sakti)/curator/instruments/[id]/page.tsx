"use client";

import { useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import { Card, ErrorState, PageHeader, SkeletonCard } from "@carebridge/ui";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeftIcon } from "@/components/icons";
import { LaneBadge } from "@/components/sakti/corpus/labels";
import { SourceRow, VersionRow } from "@/components/sakti/corpus/rows";

/** One instrument: its provisions with every version, and the sources of its text. */
export default function InstrumentPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useI18n();
  const q = useQuery((a) => a.corpus.instrument(id), [id]);
  const instrument = q.data;

  if (q.error && !instrument) return <ErrorState error={q.error} onRetry={q.reload} />;
  if (!instrument) return <SkeletonCard />;

  return (
    <>
      <PageHeader
        back={
          <Link href="/curator" className="inline-flex items-center gap-1.5 font-medium text-brand-strong hover:underline">
            <ArrowLeftIcon aria-hidden />
            {t("corpus.instrument.back")}
          </Link>
        }
        title={instrument.title}
        description={`${t(`corpus.instrumentType.${instrument.instrument_type}`)} · ${t("corpus.instrument.issuedBy", {
          issuer: instrument.issued_by,
        })}`}
        actions={<LaneBadge lane={instrument.lane} />}
      />
      {instrument.description ? <p className="-mt-3 mb-6 max-w-3xl text-small text-muted">{instrument.description}</p> : null}

      <section aria-labelledby="provisions" className="flex flex-col gap-3">
        <h2 id="provisions" className="text-subheading text-ink">
          {t("corpus.instrument.provisions")}
        </h2>
        {instrument.provisions.length === 0 ? (
          <p className="text-muted">{t("corpus.instrument.noProvisions")}</p>
        ) : (
          instrument.provisions.map((provision) => (
            <Card key={provision.id} padding="none" className="px-5 sm:px-6" aria-label={provision.locator}>
              <ul className="divide-y divide-line">
                {provision.versions.map((version) => (
                  <li key={version.id}>
                    <VersionRow version={version} />
                  </li>
                ))}
              </ul>
            </Card>
          ))
        )}
      </section>

      <section aria-labelledby="instrument-sources" className="mt-8 flex flex-col gap-3">
        <h2 id="instrument-sources" className="text-subheading text-ink">
          {t("corpus.instrument.sources")}
        </h2>
        <Card padding="none" className="px-5 sm:px-6">
          <ul className="divide-y divide-line">
            {instrument.sources.map((source) => (
              <li key={source.id}>
                <SourceRow source={source} />
              </li>
            ))}
          </ul>
        </Card>
      </section>
    </>
  );
}
