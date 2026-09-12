"use client";

import { errorMessage, useI18n } from "@carebridge/i18n";
import {
  ALLOWED_UPLOAD_TYPES,
  DOCUMENT_TYPES,
  MAX_UPLOAD_BYTES,
  UPLOAD_ACCEPT,
  type DocumentType,
  type LanguageCode,
  type MedicalDocument,
} from "@carebridge/shared-types";
import { Alert, Button, Card, CardHeader, Field, ProvenanceChip, Select, TextInput, cn, formatBytes } from "@carebridge/ui";
import { useRef, useState, type FormEvent } from "react";
import { LanguageSelect } from "./LanguageSelect";

export interface UploadInput {
  file: File;
  documentType: DocumentType;
  sourceLanguage: LanguageCode | null;
  title: string | null;
}

/** Client-side checks mirror the server's; the server remains authoritative. */
export function validateFile(file: File | null): string | null {
  if (!file) return "documents.fileRequired";
  if (!(ALLOWED_UPLOAD_TYPES as readonly string[]).includes(file.type)) return "errors.unsupported_type";
  if (file.size === 0) return "errors.empty_file";
  if (file.size > MAX_UPLOAD_BYTES) return "errors.file_too_large";
  return null;
}

export function UploadForm({
  upload,
  onUploaded,
}: {
  upload: (input: UploadInput) => Promise<MedicalDocument>;
  onUploaded?: (doc: MedicalDocument) => void;
}) {
  const { t } = useI18n();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState<DocumentType | "">("");
  const [title, setTitle] = useState("");
  const [language, setLanguage] = useState<LanguageCode | "">("");
  const [fileError, setFileError] = useState<string | null>(null);
  const [typeError, setTypeError] = useState<string | null>(null);
  const [serverError, setServerError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [done, setDone] = useState<MedicalDocument | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setDone(null);
    setServerError(null);
    const fErr = validateFile(file);
    const tErr = documentType ? null : "documents.typeRequired";
    setFileError(fErr);
    setTypeError(tErr);
    if (fErr || tErr || !file || !documentType) return;
    setBusy(true);
    try {
      const doc = await upload({
        file,
        documentType,
        sourceLanguage: language || null,
        title: title.trim() || null,
      });
      setDone(doc);
      setFile(null);
      setTitle("");
      setDocumentType("");
      setLanguage("");
      if (fileRef.current) fileRef.current.value = "";
      onUploaded?.(doc);
    } catch (err) {
      setServerError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader title={t("documents.uploadTitle")} />
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <Field label={t("documents.file")} hint={t("documents.fileHint")} error={fileError ? t(fileError) : undefined}>
          {(p) => (
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                const dropped = e.dataTransfer.files?.[0] ?? null;
                if (!dropped) return;
                setFile(dropped);
                setFileError(validateFile(dropped));
              }}
              className={cn(
                "rounded-xl border border-dashed p-4 transition-colors duration-150",
                dragging ? "border-brand bg-brand-tint" : "border-line-strong bg-sunken/70",
              )}
            >
              <input
                {...p}
                ref={fileRef}
                type="file"
                accept={UPLOAD_ACCEPT}
                onChange={(e) => {
                  const f = e.target.files?.[0] ?? null;
                  setFile(f);
                  setFileError(f ? validateFile(f) : null);
                }}
                className="block w-full cursor-pointer text-small file:mr-3 file:min-h-10 file:cursor-pointer file:rounded-md file:border-0 file:bg-brand file:px-4 file:font-semibold file:text-white"
              />
              {file ? (
                <p className="mt-3 flex flex-wrap items-center gap-2">
                  <ProvenanceChip kind="document" label={file.name} />
                  <span className="text-small text-muted">{formatBytes(file.size, t)}</span>
                </p>
              ) : null}
            </div>
          )}
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t("documents.type")} error={typeError ? t(typeError) : undefined}>
            {(p) => (
              <Select {...p} value={documentType} onChange={(e) => setDocumentType(e.target.value as DocumentType | "")}>
                <option value="">{t("documents.chooseType")}</option>
                {DOCUMENT_TYPES.map((dt) => (
                  <option key={dt} value={dt}>
                    {t(`documentType.${dt}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label={t("documents.language")}>
            {(p) => (
              <LanguageSelect {...p} value={language} onChange={setLanguage} emptyLabel={t("documents.notSpecified")} />
            )}
          </Field>
        </div>
        <Field label={t("documents.titleLabel")}>
          {(p) => <TextInput {...p} maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />}
        </Field>
        {serverError ? <Alert tone="error">{errorMessage(t, serverError)}</Alert> : null}
        {done ? (
          <Alert tone="success" title={t("documents.success")}>
            {t("documents.processingNotice")}
          </Alert>
        ) : null}
        <div>
          <Button type="submit" size="lg" loading={busy} className="max-sm:w-full">
            {busy ? t("documents.uploading") : t("documents.submit")}
          </Button>
        </div>
      </form>
    </Card>
  );
}
