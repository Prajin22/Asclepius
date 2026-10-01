"use client";

import { useApi, useQuery } from "@carebridge/api-client/react";
import { errorMessage, useI18n } from "@carebridge/i18n";
import type { CorpusSourceDetail, ProvisionVersionDetail } from "@carebridge/shared-types";
import {
  Alert,
  Button,
  Card,
  ErrorState,
  PageHeader,
  SkeletonCard,
  buttonClasses,
  formatBytes,
} from "@carebridge/ui";
import Link from "next/link";
import { useState } from "react";
import { ArrowLeftIcon } from "@/components/icons";
import { Checksum, Fact, IngestionBadge, LaneBadge, ReviewBadge } from "./labels";
import { ReviewActions } from "./ReviewActions";
import { SourceText, VersionLink } from "./SourceText";

/** One source document under review: provenance, reading, decision, text, versions. */
export function SourceReview({ id }: { id: string }) {
  const api = useApi();
  const { t, formatDate, formatDateTime } = useI18n();
  const q = useQuery((a) => a.corpus.source(id), [id]);
  const source = q.data;
  const read = source?.ingestion_state === "parsed" || source?.ingestion_state === "needs_review";
  const text = useQuery((a) => (read ? a.corpus.sourceText(id) : Promise.resolve(null)), [id, read]);
  const instrument = useQuery(
    (a) => (source ? a.corpus.instrument(source.instrument.id) : Promise.resolve(null)),
    [source?.instrument.id],
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState<string | null>(null);

  if (q.error && !source) return <ErrorState error={q.error} onRetry={q.reload} />;
  if (!source) return <SkeletonCard />;

  const update = (next: CorpusSourceDetail) => q.setData(next);
  async function act(run: () => Promise<CorpusSourceDetail>) {
    setBusy(true);
    setError(null);
    try {
      update(await run());
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  async function openOriginal() {
    const blob = await api.corpus.original(id);
    window.open(URL.createObjectURL(blob), "_blank", "noopener,noreferrer");
  }
  function created(version: ProvisionVersionDetail) {
    setNotice(t("corpus.mark.created", { number: version.version_number }));
    q.reload();
    instrument.reload();
  }

  // Versions may be cut from any source that was read and not rejected —
  // including an approved one, whose text can never change underneath them.
  const canMark = read && source.review_state !== "rejected";
  const parseErrorKey = `corpus.parseError.${source.parse_error_code ?? "generic"}`;

  return (
    <>
      <PageHeader
        back={
          <Link href="/curator" className="inline-flex items-center gap-1.5 font-medium text-brand-strong hover:underline">
            <ArrowLeftIcon aria-hidden />
            {t("corpus.source.back")}
          </Link>
        }
        title={source.title}
        description={`${source.instrument.title} · ${source.authority_name}`}
        actions={
          <div className="flex flex-wrap gap-1.5">
            <LaneBadge lane={source.lane} />
            <IngestionBadge state={source.ingestion_state} />
            <ReviewBadge state={source.review_state} />
          </div>
        }
      />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="flex min-w-0 flex-col gap-6">
          <Card aria-labelledby="provenance">
            <h2 id="provenance" className="text-subheading text-ink">
              {t("corpus.source.provenance")}
            </h2>
            <dl className="mt-2 divide-y divide-line">
              <Fact label={t("corpus.source.instrument")}>
                <Link href={`/curator/instruments/${source.instrument.id}`} className="text-brand-strong hover:underline">
                  {source.instrument.title}
                </Link>{" "}
                · {t(`corpus.instrumentType.${source.instrument.instrument_type}`)}
              </Fact>
              <Fact label={t("corpus.authority.label")}>{source.authority_name}</Fact>
              <Fact label={t("corpus.documentType.label")}>{t(`corpus.documentType.${source.document_type}`)}</Fact>
              {source.source_url ? (
                <Fact label={t("corpus.upload.sourceUrl")}>
                  <a href={source.source_url} target="_blank" rel="noopener noreferrer" className="break-all text-brand-strong hover:underline">
                    {source.source_url}
                  </a>
                </Fact>
              ) : null}
              {source.source_reference ? (
                <Fact label={t("corpus.upload.sourceReference")}>{source.source_reference}</Fact>
              ) : null}
              <Fact label={t("corpus.source.sourceDate")}>
                {source.source_date ? formatDate(source.source_date) : t("corpus.version.notRecorded")}
              </Fact>
              <Fact label={t("corpus.upload.retrievedOn")}>{formatDate(source.retrieved_on)}</Fact>
              <Fact label={t("corpus.source.terms")}>{t(`corpus.terms.${source.terms_status}`)}</Fact>
              <Fact label={t("corpus.source.fileName")}>
                {source.file_name} · {formatBytes(source.size_bytes, t)}
              </Fact>
              <Fact label={t("corpus.source.checksum")}>
                <Checksum value={source.sha256} />
              </Fact>
              {source.text_sha256 ? (
                <Fact label={t("corpus.source.textChecksum")}>
                  <Checksum value={source.text_sha256} />
                </Fact>
              ) : null}
            </dl>
            <p className="mt-3 text-caption text-subtle">
              {t("corpus.source.uploadedBy", { email: source.uploaded_by.email, date: formatDateTime(source.created_at) })}
            </p>
            <Button variant="secondary" size="sm" className="mt-3" onClick={() => void openOriginal()}>
              {t("corpus.source.openOriginal")}
            </Button>
          </Card>

          {read ? (
            <Card aria-labelledby="text-title">
              <h2 id="text-title" className="text-subheading text-ink">
                {t("corpus.source.textTitle")}
              </h2>
              {notice ? (
                <Alert tone="success" className="mt-3">
                  {notice}
                </Alert>
              ) : null}
              <div className="mt-3">
                {text.error && !text.data ? (
                  <ErrorState error={text.error} onRetry={text.reload} />
                ) : !text.data ? (
                  <SkeletonCard />
                ) : (
                  <SourceText
                    sourceId={source.id}
                    instrumentId={source.instrument.id}
                    text={text.data}
                    provisions={instrument.data?.provisions ?? []}
                    canMark={canMark}
                    onCreated={created}
                  />
                )}
              </div>
            </Card>
          ) : null}

          <Card aria-labelledby="versions-title">
            <h2 id="versions-title" className="text-subheading text-ink">
              {t("corpus.source.versionsTitle")}
            </h2>
            {source.versions.length === 0 ? (
              <p className="mt-2 text-muted">{t("corpus.source.noVersions")}</p>
            ) : (
              <ul className="mt-2 flex flex-col divide-y divide-line">
                {source.versions.map((v) => (
                  <li key={v.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
                    <VersionLink id={v.id} locator={v.provision.locator} number={v.version_number} />
                    <ReviewBadge state={v.review_state} />
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        <Card tone="quiet" aria-labelledby="decision" className="lg:sticky lg:top-24">
          <h2 id="decision" className="text-subheading text-ink">
            {t("corpus.reviewState." + source.review_state)}
          </h2>
          <div className="mt-3 flex flex-col gap-4">
            {source.ingestion_issues.length > 0 ? (
              <Alert tone="warning" title={t("corpus.source.issuesTitle")}>
                <ul className="list-disc pl-5">
                  {source.ingestion_issues.map((issue) => (
                    <li key={issue}>{t(`corpus.issue.${issue}`)}</li>
                  ))}
                </ul>
              </Alert>
            ) : null}
            {source.ingestion_state === "failed" ? (
              <Alert tone="error">
                {t(parseErrorKey) === parseErrorKey ? t("corpus.parseError.generic") : t(parseErrorKey)}
              </Alert>
            ) : null}
            {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}

            {source.review_state === "draft" && !read ? (
              <>
                <p className="text-small text-muted">{t("corpus.source.readHint")}</p>
                <Button onClick={() => act(() => api.corpus.parse(id))} disabled={busy}>
                  {busy
                    ? t("corpus.source.reading")
                    : source.ingestion_state === "failed"
                      ? t("corpus.source.readAgain")
                      : t("corpus.source.read")}
                </Button>
              </>
            ) : null}
            {source.review_state === "draft" && read ? (
              <Button onClick={() => act(() => api.corpus.submitSource(id))} disabled={busy}>
                {t("corpus.source.submit")}
              </Button>
            ) : null}
            {source.review_state === "under_review" ? (
              <ReviewActions
                checksum={source.sha256}
                needsAcknowledgment={source.ingestion_state === "needs_review"}
                onApprove={(ack) => act(() => api.corpus.approveSource(id, source.sha256, ack))}
                onReject={(reason) => act(() => api.corpus.rejectSource(id, reason))}
              />
            ) : null}
            {source.review_state === "approved" && source.approved_by && source.approved_at ? (
              <p className="text-small text-ink">
                {t("corpus.source.approvedBy", { email: source.approved_by.email, date: formatDateTime(source.approved_at) })}
              </p>
            ) : null}
            {source.review_state === "rejected" && source.rejected_by && source.rejected_at ? (
              <div className="text-small text-ink">
                <p>{t("corpus.source.rejectedBy", { email: source.rejected_by.email, date: formatDateTime(source.rejected_at) })}</p>
                {source.rejection_reason ? <p className="mt-1">{t("corpus.source.rejectionReason", { reason: source.rejection_reason })}</p> : null}
              </div>
            ) : null}
            {source.review_state === "approved" || source.review_state === "rejected" ? (
              <p className="text-small text-muted">{t("corpus.source.final")}</p>
            ) : null}
            {read ? (
              <Link href={`/curator/sources/${source.id}/diff`} className={buttonClasses("secondary", "md", "w-full")}>
                {t("corpus.source.compare")}
              </Link>
            ) : null}
          </div>
        </Card>
      </div>
    </>
  );
}
