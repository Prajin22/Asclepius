"use client";

import { useApi, useQuery } from "@carebridge/api-client/react";
import { errorMessage, useI18n } from "@carebridge/i18n";
import {
  CORPUS_DOCUMENT_TYPES,
  CORPUS_LANES,
  INSTRUMENT_TYPES,
  type CorpusDocumentType,
  type CorpusLane,
  type InstrumentType,
  type SourceAuthority,
} from "@carebridge/shared-types";
import { Alert, Button, Card, Field, PageHeader, Select, TextArea, TextInput } from "@carebridge/ui";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

const NEW = "__new__";

function today(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/**
 * Upload one official source with its provenance. The file is stored as it is;
 * nothing is read or approved here. The lane is chosen first and fixes what the
 * rest of the form can offer: the instruments and the authorities of that lane.
 */
export function CuratorUpload() {
  const api = useApi();
  const router = useRouter();
  const { t } = useI18n();

  const [lane, setLane] = useState<CorpusLane>("india");
  const instruments = useQuery((a) => a.corpus.instruments(lane), [lane]);
  const authorities = useQuery((a) => a.corpus.authorities());

  const [instrumentId, setInstrumentId] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [newType, setNewType] = useState<InstrumentType>("act");
  const [issuedBy, setIssuedBy] = useState("");
  const [description, setDescription] = useState("");

  const [title, setTitle] = useState("");
  const [authority, setAuthority] = useState<SourceAuthority | "">("");
  const [documentType, setDocumentType] = useState<CorpusDocumentType>("original_text");
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceReference, setSourceReference] = useState("");
  const [sourceDate, setSourceDate] = useState("");
  const [retrievedOn, setRetrievedOn] = useState(today);
  const [file, setFile] = useState<File | null>(null);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const laneAuthorities = (authorities.data ?? []).filter((a) => a.lane === lane);
  const chosenInstrument = instrumentId || (instruments.data?.[0]?.id ?? NEW);
  const creatingInstrument = chosenInstrument === NEW;
  const chosenAuthority = authority || laneAuthorities[0]?.code || "";
  const ready =
    Boolean(file && title.trim() && chosenAuthority && retrievedOn) &&
    Boolean(sourceUrl.trim() || sourceReference.trim()) &&
    (!creatingInstrument || Boolean(newTitle.trim() && issuedBy.trim()));

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!file || !chosenAuthority) return;
    setBusy(true);
    setError(null);
    try {
      const instrument = creatingInstrument
        ? await api.corpus.createInstrument({
            lane,
            instrument_type: newType,
            title: newTitle.trim(),
            issued_by: issuedBy.trim(),
            description: description.trim() || null,
          })
        : { id: chosenInstrument };
      if (creatingInstrument) setInstrumentId(instrument.id);
      const source = await api.corpus.uploadSource({
        file,
        lane,
        instrumentId: instrument.id,
        title: title.trim(),
        sourceAuthority: chosenAuthority as SourceAuthority,
        documentType,
        retrievedOn,
        sourceUrl: sourceUrl.trim() || null,
        sourceReference: sourceReference.trim() || null,
        sourceDate: sourceDate || null,
      });
      router.push(`/curator/sources/${source.id}`);
    } catch (err) {
      setError(err);
      instruments.reload();
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title={t("pages.upload.title")} description={t("pages.upload.description")} />
      <form onSubmit={submit} className="flex max-w-3xl flex-col gap-5" noValidate>
        <Card>
          <Field label={t("corpus.lane.label")} hint={t("corpus.lane.hint")}>
            {(p) => (
              <Select
                {...p}
                value={lane}
                onChange={(e) => {
                  setLane(e.target.value as CorpusLane);
                  setInstrumentId("");
                  setAuthority("");
                }}
              >
                {CORPUS_LANES.map((l) => (
                  <option key={l} value={l}>
                    {t(`corpus.lane.${l}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </Card>

        <Card aria-labelledby="upload-instrument">
          <h2 id="upload-instrument" className="text-subheading text-ink">
            {t("corpus.upload.instrumentTitle")}
          </h2>
          <p className="mt-1 text-small text-muted">{t("corpus.upload.instrumentHint")}</p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Field label={t("corpus.upload.chooseInstrument")} className="sm:col-span-2">
              {(p) => (
                <Select {...p} value={chosenInstrument} onChange={(e) => setInstrumentId(e.target.value)}>
                  {(instruments.data ?? []).map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.title} · {t(`corpus.instrumentType.${i.instrument_type}`)}
                    </option>
                  ))}
                  <option value={NEW}>{t("corpus.upload.newInstrument")}</option>
                </Select>
              )}
            </Field>
            {creatingInstrument ? (
              <>
                <Field label={t("corpus.upload.instrumentTitleLabel")} className="sm:col-span-2">
                  {(p) => <TextInput {...p} maxLength={500} value={newTitle} onChange={(e) => setNewTitle(e.target.value)} />}
                </Field>
                <Field label={t("corpus.instrumentType.label")}>
                  {(p) => (
                    <Select {...p} value={newType} onChange={(e) => setNewType(e.target.value as InstrumentType)}>
                      {INSTRUMENT_TYPES.map((type) => (
                        <option key={type} value={type}>
                          {t(`corpus.instrumentType.${type}`)}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
                <Field label={t("corpus.upload.issuedBy")} hint={t("corpus.upload.issuedByHint")}>
                  {(p) => <TextInput {...p} maxLength={300} value={issuedBy} onChange={(e) => setIssuedBy(e.target.value)} />}
                </Field>
                <Field
                  label={t("corpus.upload.description")}
                  hint={t("corpus.upload.descriptionHint")}
                  className="sm:col-span-2"
                >
                  {(p) => (
                    <TextArea {...p} rows={2} maxLength={2000} value={description} onChange={(e) => setDescription(e.target.value)} />
                  )}
                </Field>
              </>
            ) : null}
          </div>
        </Card>

        <Card aria-labelledby="upload-source">
          <h2 id="upload-source" className="text-subheading text-ink">
            {t("corpus.upload.sourceTitle")}
          </h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Field label={t("corpus.upload.documentTitle")} className="sm:col-span-2">
              {(p) => <TextInput {...p} maxLength={500} value={title} onChange={(e) => setTitle(e.target.value)} />}
            </Field>
            <Field label={t("corpus.authority.label")} hint={t("corpus.authority.hint")}>
              {(p) => (
                <Select {...p} value={chosenAuthority} onChange={(e) => setAuthority(e.target.value as SourceAuthority)}>
                  {laneAuthorities.map((a) => (
                    <option key={a.code} value={a.code}>
                      {t(`corpus.authority.${a.code}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t("corpus.documentType.label")}>
              {(p) => (
                <Select {...p} value={documentType} onChange={(e) => setDocumentType(e.target.value as CorpusDocumentType)}>
                  {CORPUS_DOCUMENT_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {t(`corpus.documentType.${type}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t("corpus.upload.sourceUrl")} hint={t("corpus.upload.sourceUrlHint")} className="sm:col-span-2">
              {(p) => (
                <TextInput {...p} type="url" inputMode="url" maxLength={2000} value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} />
              )}
            </Field>
            <Field
              label={t("corpus.upload.sourceReference")}
              hint={t("corpus.upload.sourceReferenceHint")}
              className="sm:col-span-2"
            >
              {(p) => (
                <TextInput {...p} maxLength={1000} value={sourceReference} onChange={(e) => setSourceReference(e.target.value)} />
              )}
            </Field>
            <p className="text-small text-muted sm:col-span-2">{t("corpus.upload.provenanceNote")}</p>
            <Field label={t("corpus.upload.sourceDate")}>
              {(p) => <TextInput {...p} type="date" value={sourceDate} onChange={(e) => setSourceDate(e.target.value)} />}
            </Field>
            <Field label={t("corpus.upload.retrievedOn")}>
              {(p) => <TextInput {...p} type="date" value={retrievedOn} onChange={(e) => setRetrievedOn(e.target.value)} />}
            </Field>
            <Field label={t("corpus.upload.file")} hint={t("corpus.upload.fileHint")} className="sm:col-span-2">
              {(p) => (
                <input
                  {...p}
                  type="file"
                  accept="application/pdf,.pdf"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  className="block w-full cursor-pointer text-small file:mr-3 file:min-h-10 file:cursor-pointer file:rounded-md file:border-0 file:bg-brand file:px-4 file:font-semibold file:text-white"
                />
              )}
            </Field>
          </div>
        </Card>

        {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
        <div>
          <Button type="submit" disabled={busy || !ready}>
            {busy ? t("corpus.upload.submitting") : t("corpus.upload.submit")}
          </Button>
        </div>
      </form>
    </>
  );
}
