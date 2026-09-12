"use client";

import { errorMessage, useI18n } from "@carebridge/i18n";
import type { LanguageCode, MedicalRecord, MedicalRecordCreate, RecordSource, RecordStatus } from "@carebridge/shared-types";
import { RECORD_SOURCES } from "@carebridge/shared-types";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  LanguageTag,
  Select,
  SourceBadge,
  TextArea,
  TextInput,
} from "@carebridge/ui";
import { useState, type FormEvent } from "react";
import { LanguageSelect } from "./LanguageSelect";

export type EditableType = "condition" | "allergy" | "medication" | "history_note" | "family_history";

/** Types that describe a standing state and therefore carry current/past status. */
const HAS_STATUS: readonly EditableType[] = ["condition", "allergy", "medication"];

export interface RecordFormValues {
  title: string;
  content: string;
  source_language: LanguageCode;
  status: RecordStatus;
}

export function SourceLegend() {
  const { t } = useI18n();
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-small">
      <span className="font-semibold text-muted">{t("source.legend")}:</span>
      {RECORD_SOURCES.map((s: RecordSource) => (
        <SourceBadge key={s} source={s} />
      ))}
    </div>
  );
}

export function RecordForm({
  type,
  initial,
  onSubmit,
  onCancel,
}: {
  type: EditableType;
  initial?: MedicalRecord;
  onSubmit: (values: RecordFormValues) => Promise<void>;
  onCancel: () => void;
}) {
  const { t, locale } = useI18n();
  const [title, setTitle] = useState(initial?.title ?? "");
  const [content, setContent] = useState(initial?.content ?? "");
  const [lang, setLang] = useState<LanguageCode | "">(initial?.source_language ?? (locale as LanguageCode));
  const [status, setStatus] = useState<RecordStatus>(initial?.status ?? "active");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!title.trim() || !lang) return;
    setBusy(true);
    setError(null);
    try {
      await onSubmit({ title: title.trim(), content: content.trim(), source_language: lang, status });
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-3 flex flex-col gap-4 rounded-lg border border-line bg-sunken p-4">
      <Field label={t("health.form.title")} hint={t(`health.form.titleHint.${type}`)}>
        {(p) => <TextInput {...p} required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />}
      </Field>
      <Field label={t("health.form.details")} hint={t("health.form.detailsHint")}>
        {(p) => (
          <TextArea
            {...p}
            rows={3}
            lang={lang || undefined}
            maxLength={10000}
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
        )}
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("health.form.language")}>{(p) => <LanguageSelect {...p} value={lang} onChange={setLang} />}</Field>
        {HAS_STATUS.includes(type) ? (
          <Field label={t("health.form.status")}>
            {(p) => (
              <Select {...p} value={status} onChange={(e) => setStatus(e.target.value as RecordStatus)}>
                <option value="active">{t("recordStatus.active")}</option>
                <option value="resolved">{t("recordStatus.resolved")}</option>
              </Select>
            )}
          </Field>
        ) : null}
      </div>
      {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={busy || !title.trim()}>
          {busy ? t("actions.saving") : t("actions.save")}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={busy}>
          {t("actions.cancel")}
        </Button>
      </div>
    </form>
  );
}

function RecordItem({
  record,
  editing,
  onEdit,
  onDelete,
  editor,
}: {
  record: MedicalRecord;
  editing: boolean;
  onEdit: () => void;
  onDelete: () => void;
  editor: React.ReactNode;
}) {
  const { t, formatDate } = useI18n();
  const title = record.title ?? t(`recordType.${record.type}`);
  const editable = record.source === "patient";
  return (
    <li className="py-4 first:pt-0 last:pb-0">
      <p className="font-semibold text-ink">{title}</p>
      {record.content ? (
        <p lang={record.source_language} className="mt-0.5 whitespace-pre-line">
          {record.content}
        </p>
      ) : null}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <SourceBadge source={record.source} />
        {record.status === "resolved" ? <Badge>{t("recordStatus.resolved")}</Badge> : null}
        <LanguageTag code={record.source_language} />
        <span className="text-caption text-muted">{t("health.recorded", { date: formatDate(record.created_at) })}</span>
        {/* Actions share the metadata row, so they never squeeze the patient's own words. */}
        {editable && !editing ? (
          <span className="-mr-2 ml-auto flex gap-1">
            <Button variant="ghost" size="sm" aria-label={`${t("actions.edit")}: ${title}`} onClick={onEdit}>
              {t("actions.edit")}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="text-danger hover:bg-danger-soft"
              aria-label={`${t("actions.delete")}: ${title}`}
              onClick={onDelete}
            >
              {t("actions.delete")}
            </Button>
          </span>
        ) : null}
      </div>
      {editing ? editor : null}
    </li>
  );
}

export function RecordSection({
  title,
  records,
  addType,
  onCreate,
  onUpdate,
  onDelete,
}: {
  title: string;
  records: MedicalRecord[];
  addType?: EditableType;
  onCreate: (data: MedicalRecordCreate) => Promise<void>;
  onUpdate: (id: string, values: RecordFormValues) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}) {
  const { t } = useI18n();
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  return (
    <Card>
      <CardHeader
        title={title}
        action={
          addType && !adding ? (
            <Button variant="secondary" size="sm" onClick={() => setAdding(true)}>
              {t("health.add")}
            </Button>
          ) : null
        }
      />
      {records.length === 0 && !adding ? <p className="text-muted">{t("health.empty")}</p> : null}
      {records.length > 0 ? (
        <ul className="divide-y divide-line">
          {records.map((r) => (
            <RecordItem
              key={r.id}
              record={r}
              editing={editingId === r.id}
              onEdit={() => setEditingId(r.id)}
              onDelete={async () => {
                if (window.confirm(t("health.confirmDelete"))) await onDelete(r.id);
              }}
              editor={
                <RecordForm
                  type={(r.type === "current_problem" ? "history_note" : r.type) as EditableType}
                  initial={r}
                  onCancel={() => setEditingId(null)}
                  onSubmit={async (values) => {
                    await onUpdate(r.id, values);
                    setEditingId(null);
                  }}
                />
              }
            />
          ))}
        </ul>
      ) : null}
      {adding && addType ? (
        <div>
          <h3 className="mt-2 font-semibold">{t(`health.addTitle.${addType}`)}</h3>
          <RecordForm
            type={addType}
            onCancel={() => setAdding(false)}
            onSubmit={async (values) => {
              await onCreate({ type: addType, ...values });
              setAdding(false);
            }}
          />
        </div>
      ) : null}
    </Card>
  );
}
