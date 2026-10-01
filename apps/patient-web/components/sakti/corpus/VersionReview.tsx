"use client";

import { useApi, useQuery } from "@carebridge/api-client/react";
import { errorMessage, useI18n } from "@carebridge/i18n";
import type { ProvisionVersionDetail } from "@carebridge/shared-types";
import { Alert, Button, Card, ErrorState, Field, PageHeader, SkeletonCard, TextInput } from "@carebridge/ui";
import Link from "next/link";
import { useState } from "react";
import { ArrowLeftIcon } from "@/components/icons";
import { DiffView } from "./DiffView";
import { Checksum, Fact, LaneBadge, ReviewBadge, pageRange } from "./labels";
import { ReviewActions } from "./ReviewActions";
import { StatusHistory } from "./StatusHistory";

/** One provision version: its exact text, where it came from, how it differs, and its status history. */
export function VersionReview({ id }: { id: string }) {
  const api = useApi();
  const { t, formatDate, formatDateTime } = useI18n();
  const q = useQuery((a) => a.corpus.version(id), [id]);
  const diff = useQuery((a) => a.corpus.versionDiff(id), [id]);
  const version = q.data;
  const approvedSources = useQuery(
    (a) => (version ? a.corpus.sources({ lane: version.lane, reviewState: "approved" }) : Promise.resolve([])),
    [version?.lane],
  );
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  if (q.error && !version) return <ErrorState error={q.error} onRetry={q.reload} />;
  if (!version) return <SkeletonCard />;

  async function act(run: () => Promise<ProvisionVersionDetail>) {
    setBusy(true);
    setError(null);
    try {
      q.setData(await run());
      diff.reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const sourceApproved = version.source.review_state === "approved";

  return (
    <>
      <PageHeader
        back={
          <Link
            href={`/curator/sources/${version.source.id}`}
            className="inline-flex items-center gap-1.5 font-medium text-brand-strong hover:underline"
          >
            <ArrowLeftIcon aria-hidden />
            {version.source.title}
          </Link>
        }
        title={t("corpus.version.title", { locator: version.provision.locator, number: version.version_number })}
        description={`${version.instrument.title} · ${t(`corpus.locatorType.${version.provision.locator_type}`)}`}
        actions={
          <div className="flex flex-wrap gap-1.5">
            <LaneBadge lane={version.lane} />
            <ReviewBadge state={version.review_state} />
          </div>
        }
      />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="flex min-w-0 flex-col gap-6">
          <Card tone="paper" aria-labelledby="exact-text">
            <h2 id="exact-text" className="text-subheading text-ink">
              {t("corpus.version.textTitle")}
            </h2>
            <p className="mt-1 text-small text-muted">
              {t("corpus.version.textFrom", { source: version.source.title })} ·{" "}
              {pageRange(t, version.page_start, version.page_end)}
            </p>
            {version.ocr_derived ? (
              <Alert tone="warning" className="mt-3">
                {t("corpus.version.ocrWarning")}
              </Alert>
            ) : null}
            <blockquote className="mt-3 whitespace-pre-wrap break-words font-mono text-small leading-relaxed text-ink">
              {version.text}
            </blockquote>
            <p className="mt-4 border-t border-paper-line pt-3 text-caption text-muted">
              {t("corpus.version.checksum")}
              <Checksum value={version.text_sha256} className="mt-0.5 block" />
            </p>
          </Card>

          <Card aria-labelledby="version-diff">
            <h2 id="version-diff" className="text-subheading text-ink">
              {t("corpus.version.diffTitle")}
            </h2>
            <div className="mt-3">
              {diff.error && !diff.data ? (
                <ErrorState error={diff.error} onRetry={diff.reload} />
              ) : !diff.data ? (
                <SkeletonCard />
              ) : (
                <DiffView diff={diff.data} noBaseline={t("corpus.version.noBaseline")} />
              )}
            </div>
          </Card>

          <Card aria-labelledby="status-history">
            <h2 id="status-history" className="text-subheading text-ink">
              {t("corpus.version.statusTitle")}
            </h2>
            <div className="mt-3">
              <StatusHistory
                versionId={version.id}
                events={version.status_events}
                approvedSources={approvedSources.data ?? []}
                canRecord={version.review_state === "approved"}
                onRecorded={() => q.reload()}
              />
            </div>
          </Card>
        </div>

        <div className="flex flex-col gap-6 lg:sticky lg:top-24">
          <Card tone="quiet" aria-labelledby="version-facts">
            <h2 id="version-facts" className="text-subheading text-ink">
              {t(`corpus.reviewState.${version.review_state}`)}
            </h2>
            <dl className="mt-2 divide-y divide-line">
              <Fact stacked label={t("corpus.version.validity")}>
                {t("corpus.version.validityRange", {
                  from: version.valid_from ? formatDate(version.valid_from) : t("corpus.version.notRecorded"),
                  to: version.valid_to ? formatDate(version.valid_to) : t("corpus.version.notRecorded"),
                })}
              </Fact>
            </dl>
            {version.approved_by && version.approved_at ? (
              <p className="mt-3 text-small text-ink">
                {t("corpus.source.approvedBy", { email: version.approved_by.email, date: formatDateTime(version.approved_at) })}
              </p>
            ) : null}
            {version.rejected_by && version.rejected_at ? (
              <div className="mt-3 text-small text-ink">
                <p>{t("corpus.source.rejectedBy", { email: version.rejected_by.email, date: formatDateTime(version.rejected_at) })}</p>
                {version.rejection_reason ? (
                  <p className="mt-1">{t("corpus.source.rejectionReason", { reason: version.rejection_reason })}</p>
                ) : null}
              </div>
            ) : null}
            <div className="mt-4 flex flex-col gap-4">
              {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
              {version.review_state === "draft" ? (
                <>
                  <DraftDates version={version} onSaved={(next) => q.setData(next)} />
                  <Button onClick={() => act(() => api.corpus.submitVersion(id))} disabled={busy}>
                    {t("corpus.version.submit")}
                  </Button>
                </>
              ) : null}
              {version.review_state === "under_review" ? (
                <ReviewActions
                  checksum={version.text_sha256}
                  needsAcknowledgment={version.ocr_derived}
                  blocked={sourceApproved ? undefined : t("corpus.review.needsSource")}
                  onApprove={(ack) => act(() => api.corpus.approveVersion(id, version.text_sha256, ack))}
                  onReject={(reason) => act(() => api.corpus.rejectVersion(id, reason))}
                />
              ) : null}
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}

function DraftDates({ version, onSaved }: { version: ProvisionVersionDetail; onSaved: (v: ProvisionVersionDetail) => void }) {
  const api = useApi();
  const { t } = useI18n();
  const [validFrom, setValidFrom] = useState(version.valid_from ?? "");
  const [validTo, setValidTo] = useState(version.valid_to ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      onSaved(await api.corpus.updateVersion(version.id, { valid_from: validFrom || null, valid_to: validTo || null }));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <Field label={t("corpus.mark.validFrom")}>
        {(p) => <TextInput {...p} type="date" value={validFrom} onChange={(e) => setValidFrom(e.target.value)} />}
      </Field>
      <Field label={t("corpus.mark.validTo")} hint={t("corpus.mark.validityHint")}>
        {(p) => <TextInput {...p} type="date" value={validTo} onChange={(e) => setValidTo(e.target.value)} />}
      </Field>
      {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
      <Button variant="secondary" onClick={save} disabled={busy}>
        {t("corpus.version.editDates")}
      </Button>
    </div>
  );
}
