"use client";

import { useApi } from "@carebridge/api-client/react";
import { errorMessage, useI18n } from "@carebridge/i18n";
import {
  PROVISION_STATUSES,
  type CorpusSourceSummary,
  type ProvisionStatus,
  type StatusEvent,
} from "@carebridge/shared-types";
import { Alert, Button, Field, Select, TextArea, TextInput } from "@carebridge/ui";
import { useState } from "react";

/**
 * The append-only status history of one approved version, and the form that
 * adds to it. Each entry records what a cited source states, with that source;
 * nothing here is the system's own view of the law.
 */
export function StatusHistory({
  versionId,
  events,
  approvedSources,
  canRecord,
  onRecorded,
}: {
  versionId: string;
  events: StatusEvent[];
  approvedSources: CorpusSourceSummary[];
  canRecord: boolean;
  onRecorded: (event: StatusEvent) => void;
}) {
  const { t, formatDate, formatDateTime } = useI18n();
  return (
    <div className="flex flex-col gap-4">
      <p className="text-small text-muted">{t("corpus.version.statusNote")}</p>
      {events.length === 0 ? (
        <p className="text-muted">{t("corpus.version.noStatus")}</p>
      ) : (
        <ol className="flex flex-col divide-y divide-line">
          {events.map((event) => (
            <li key={event.id} className="py-3 first:pt-0">
              <p className="font-semibold text-ink">
                {t(`corpus.status.${event.status}`)}
                {event.effective_date ? <span className="font-normal text-muted"> · {formatDate(event.effective_date)}</span> : null}
              </p>
              {event.basis_source ? <p className="text-small text-ink">{event.basis_source.title}</p> : null}
              {event.basis_reference ? <p className="text-small text-ink">{event.basis_reference}</p> : null}
              {event.note ? <p className="text-small text-muted">{event.note}</p> : null}
              <p className="text-caption text-subtle">
                {t("corpus.version.recordedBy", { email: event.recorded_by.email, date: formatDateTime(event.recorded_at) })}
              </p>
            </li>
          ))}
        </ol>
      )}
      {canRecord ? (
        <RecordStatusForm versionId={versionId} approvedSources={approvedSources} onRecorded={onRecorded} />
      ) : null}
    </div>
  );
}

function RecordStatusForm({
  versionId,
  approvedSources,
  onRecorded,
}: {
  versionId: string;
  approvedSources: CorpusSourceSummary[];
  onRecorded: (event: StatusEvent) => void;
}) {
  const api = useApi();
  const { t } = useI18n();
  const [status, setStatus] = useState<ProvisionStatus>("in_force");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [basisSourceId, setBasisSourceId] = useState("");
  const [basisReference, setBasisReference] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const hasBasis = Boolean(basisSourceId || basisReference.trim());

  async function record() {
    setBusy(true);
    setError(null);
    try {
      const event = await api.corpus.recordStatus(versionId, {
        status,
        effective_date: effectiveDate || null,
        basis_source_id: basisSourceId || null,
        basis_reference: basisReference.trim() || null,
        note: note.trim() || null,
      });
      setEffectiveDate("");
      setBasisSourceId("");
      setBasisReference("");
      setNote("");
      onRecorded(event);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="flex flex-col gap-4 border-t border-line pt-4"
      onSubmit={(e) => {
        e.preventDefault();
        void record();
      }}
      aria-labelledby="record-status"
    >
      <h3 id="record-status" className="text-subheading text-ink">
        {t("corpus.version.recordStatus")}
      </h3>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("corpus.status.label")}>
          {(p) => (
            <Select {...p} value={status} onChange={(e) => setStatus(e.target.value as ProvisionStatus)}>
              {PROVISION_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {t(`corpus.status.${s}`)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label={t("corpus.version.effectiveDate")}>
          {(p) => <TextInput {...p} type="date" value={effectiveDate} onChange={(e) => setEffectiveDate(e.target.value)} />}
        </Field>
        <Field label={t("corpus.version.basisSource")} className="sm:col-span-2">
          {(p) => (
            <Select {...p} value={basisSourceId} onChange={(e) => setBasisSourceId(e.target.value)}>
              <option value="">{t("corpus.version.basisNone")}</option>
              {approvedSources.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.title} · {s.authority_name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label={t("corpus.version.basisReference")} hint={t("corpus.version.basisHint")} className="sm:col-span-2">
          {(p) => (
            <TextInput {...p} maxLength={1000} value={basisReference} onChange={(e) => setBasisReference(e.target.value)} />
          )}
        </Field>
        <Field label={t("corpus.version.note")} className="sm:col-span-2">
          {(p) => <TextArea {...p} rows={2} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} />}
        </Field>
      </div>
      {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
      <div>
        <Button type="submit" disabled={busy || !hasBasis}>
          {busy ? t("corpus.version.recording") : t("corpus.version.record")}
        </Button>
      </div>
    </form>
  );
}
