"use client";

import { useApi, useQuery } from "@carebridge/api-client/react";
import { errorMessage, useI18n } from "@carebridge/i18n";
import {
  CORPUS_DOCUMENT_TYPES,
  CORPUS_LANES,
  INSTRUMENT_TYPES,
  type CorpusDocumentType,
  type CorpusLane,
  type CorpusSourceDetail,
  type InstrumentType,
  type SourceAuthority,
} from "@carebridge/shared-types";
import { Alert, Button, Field, PageHeader, Select, TextArea, TextInput, buttonClasses, cn, formatBytes } from "@carebridge/ui";
import { Check, FilePdf, UploadSimple } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useState, type DragEvent, type ReactNode } from "react";
import { LaneMark } from "../ui";
import { Checksum, Fact, IngestionBadge, ReviewBadge } from "./labels";

const NEW = "__new__";
const STEPS = ["select", "metadata", "parse", "review", "submit"] as const;
type Step = (typeof STEPS)[number];

function today(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/**
 * Adding one official source, in five steps that compose the corpus API as it
 * already is: choose the lane and file; record what it is and where it came
 * from, and store it unchanged; read its text; review what was stored and read;
 * submit it for review. Nothing is approved here, and nothing is used until a
 * curator approves it on Approve.
 */
export function CuratorUpload() {
  const api = useApi();
  const { t } = useI18n();
  const [step, setStep] = useState<Step>("select");

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

  const [source, setSource] = useState<CorpusSourceDetail | null>(null);
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

  async function run(action: () => Promise<CorpusSourceDetail>, next?: Step) {
    setBusy(true);
    setError(null);
    try {
      setSource(await action());
      if (next) setStep(next);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function upload() {
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
      const stored = await api.corpus.uploadSource({
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
      setSource(stored);
      setStep("parse");
    } catch (err) {
      setError(err);
      instruments.reload();
    } finally {
      setBusy(false);
    }
  }

  const read = source?.ingestion_state === "parsed" || source?.ingestion_state === "needs_review";
  const index = STEPS.indexOf(step);

  return (
    <>
      <PageHeader title={t("pages.upload.title")} description={t("pages.upload.description")} />
      <div className="grid gap-6 lg:grid-cols-[14rem_minmax(0,1fr)]">
        <WizardSteps current={index} />
        <div className="flex min-w-0 max-w-3xl flex-col gap-5">
          {step === "select" ? (
            <Panel title={t("corpus.wizard.steps.select")} hint={t("corpus.wizard.selectHint")}>
              <fieldset className="flex flex-col gap-2">
                <legend className="mb-2 text-small font-semibold text-ink">{t("corpus.lane.label")}</legend>
                <div className="grid gap-2.5 sm:grid-cols-2">
                  {CORPUS_LANES.map((l) => (
                    <label
                      key={l}
                      className={cn(
                        "flex cursor-pointer items-start gap-3 rounded-md border px-4 py-3.5 transition-colors duration-150",
                        lane === l ? "border-brand bg-brand-tint ring-1 ring-brand" : "border-line hover:bg-sunken",
                      )}
                    >
                      <input
                        type="radio"
                        name="lane"
                        value={l}
                        checked={lane === l}
                        onChange={() => {
                          setLane(l);
                          setInstrumentId("");
                          setAuthority("");
                        }}
                        className="mt-1 size-5 shrink-0 accent-[var(--color-brand)]"
                      />
                      <span className="min-w-0">
                        <LaneMark lane={l} size="sm" />
                        <span className="mt-1.5 block text-small text-muted">{t(`corpus.wizard.lane.${l}`)}</span>
                      </span>
                    </label>
                  ))}
                </div>
                <p className="text-small text-muted">{t("corpus.lane.hint")}</p>
              </fieldset>
              <FileDrop file={file} onFile={setFile} />
              <Actions>
                <Button onClick={() => setStep("metadata")} disabled={!file}>
                  {t("corpus.wizard.next")}
                </Button>
              </Actions>
            </Panel>
          ) : null}

          {step === "metadata" ? (
            <Panel title={t("corpus.wizard.steps.metadata")} hint={t("corpus.upload.instrumentHint")}>
              <div className="grid gap-4 sm:grid-cols-2">
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
                    <Field label={t("corpus.upload.description")} hint={t("corpus.upload.descriptionHint")} className="sm:col-span-2">
                      {(p) => (
                        <TextArea {...p} rows={2} maxLength={2000} value={description} onChange={(e) => setDescription(e.target.value)} />
                      )}
                    </Field>
                  </>
                ) : null}
              </div>

              <h3 className="mt-2 border-t border-line pt-5 text-subheading text-ink">{t("corpus.upload.sourceTitle")}</h3>
              <div className="grid gap-4 sm:grid-cols-2">
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
                <Field label={t("corpus.upload.sourceReference")} hint={t("corpus.upload.sourceReferenceHint")} className="sm:col-span-2">
                  {(p) => <TextInput {...p} maxLength={1000} value={sourceReference} onChange={(e) => setSourceReference(e.target.value)} />}
                </Field>
                <p className="text-small text-muted sm:col-span-2">{t("corpus.upload.provenanceNote")}</p>
                <Field label={t("corpus.upload.sourceDate")}>
                  {(p) => <TextInput {...p} type="date" value={sourceDate} onChange={(e) => setSourceDate(e.target.value)} />}
                </Field>
                <Field label={t("corpus.upload.retrievedOn")}>
                  {(p) => <TextInput {...p} type="date" value={retrievedOn} onChange={(e) => setRetrievedOn(e.target.value)} />}
                </Field>
              </div>
              {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
              <p className="text-small text-muted">{t("corpus.upload.fileHint")}</p>
              <Actions>
                <Button variant="secondary" onClick={() => setStep("select")} disabled={busy}>
                  {t("corpus.wizard.back")}
                </Button>
                <Button onClick={upload} disabled={busy || !ready}>
                  <UploadSimple size={18} aria-hidden />
                  {busy ? t("corpus.upload.submitting") : t("corpus.upload.submit")}
                </Button>
              </Actions>
            </Panel>
          ) : null}

          {step === "parse" && source ? (
            <Panel title={t("corpus.wizard.steps.parse")} hint={t("corpus.source.readHint")}>
              <Alert tone="success">{t("corpus.wizard.stored")}</Alert>
              <dl className="divide-y divide-line">
                <Fact label={t("corpus.source.fileName")}>
                  {source.file_name} · {formatBytes(source.size_bytes, t)}
                </Fact>
                <Fact label={t("corpus.source.checksum")}>
                  <Checksum value={source.sha256} />
                </Fact>
                <Fact label={t("corpus.wizard.ingestion")}>
                  <IngestionBadge state={source.ingestion_state} />
                </Fact>
              </dl>
              {source.ingestion_state === "failed" ? (
                <Alert tone="error">{t(`corpus.parseError.${source.parse_error_code ?? "generic"}`)}</Alert>
              ) : null}
              {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
              <Actions>
                {read ? (
                  <Button onClick={() => setStep("review")}>{t("corpus.wizard.next")}</Button>
                ) : (
                  <Button onClick={() => run(() => api.corpus.parse(source.id))} disabled={busy}>
                    {busy
                      ? t("corpus.source.reading")
                      : source.ingestion_state === "failed"
                        ? t("corpus.source.readAgain")
                        : t("corpus.source.read")}
                  </Button>
                )}
                <Link href={`/curator/sources/${source.id}`} className={buttonClasses("ghost", "md")}>
                  {t("corpus.wizard.openSource")}
                </Link>
              </Actions>
            </Panel>
          ) : null}

          {step === "review" && source ? (
            <Panel title={t("corpus.wizard.steps.review")} hint={t("corpus.wizard.reviewHint")}>
              <dl className="divide-y divide-line">
                <Fact label={t("corpus.source.fileName")}>{source.file_name}</Fact>
                <Fact label={t("corpus.source.size")}>{formatBytes(source.size_bytes, t)}</Fact>
                <Fact label={t("corpus.wizard.pages")}>{source.page_count ?? "—"}</Fact>
                <Fact label={t("corpus.source.checksum")}>
                  <Checksum value={source.sha256} />
                </Fact>
                <Fact label={t("corpus.authority.label")}>{source.authority_name}</Fact>
                <Fact label={t("corpus.wizard.jurisdiction")}>
                  <LaneMark lane={source.lane} size="sm" />
                </Fact>
                <Fact label={t("corpus.source.instrument")}>{source.instrument.title}</Fact>
                <Fact label={t("corpus.wizard.ingestion")}>
                  <IngestionBadge state={source.ingestion_state} />
                </Fact>
                <Fact label={t("corpus.status.label")}>
                  <ReviewBadge state={source.review_state} />
                </Fact>
              </dl>
              {source.ingestion_issues.length ? (
                <Alert tone="warning" title={t("corpus.source.issuesTitle")}>
                  <ul className="flex list-disc flex-col gap-1 pl-4">
                    {source.ingestion_issues.map((issue) => (
                      <li key={issue}>{t(`corpus.issue.${issue}`)}</li>
                    ))}
                  </ul>
                </Alert>
              ) : null}
              <Actions>
                <Button onClick={() => setStep("submit")}>{t("corpus.wizard.next")}</Button>
                <Link href={`/curator/sources/${source.id}`} className={buttonClasses("secondary", "md")}>
                  {t("corpus.wizard.openText")}
                </Link>
              </Actions>
            </Panel>
          ) : null}

          {step === "submit" && source ? (
            <Panel title={t("corpus.wizard.steps.submit")} hint={t("corpus.wizard.submitHint")}>
              {source.review_state === "under_review" ? (
                <Alert tone="success" title={t("corpus.wizard.submitted")}>
                  {t("corpus.wizard.submittedBody")}
                </Alert>
              ) : null}
              <dl className="divide-y divide-line">
                <Fact label={t("corpus.upload.documentTitle")}>{source.title}</Fact>
                <Fact label={t("corpus.status.label")}>
                  <ReviewBadge state={source.review_state} />
                </Fact>
              </dl>
              {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
              <Actions>
                {source.review_state === "draft" ? (
                  <>
                    <Button variant="secondary" onClick={() => setStep("review")} disabled={busy}>
                      {t("corpus.wizard.back")}
                    </Button>
                    <Button onClick={() => run(() => api.corpus.submitSource(source.id))} disabled={busy}>
                      {t("corpus.source.submit")}
                    </Button>
                  </>
                ) : (
                  <>
                    <Link href="/curator/approve" className={buttonClasses("primary", "md")}>
                      {t("corpus.wizard.toApprove")}
                    </Link>
                    <Link href={`/curator/sources/${source.id}`} className={buttonClasses("secondary", "md")}>
                      {t("corpus.wizard.openSource")}
                    </Link>
                  </>
                )}
              </Actions>
            </Panel>
          ) : null}
        </div>
      </div>
    </>
  );
}

/** The five steps. Desktop: a vertical list; phone: one line and a track. */
function WizardSteps({ current }: { current: number }) {
  const { t } = useI18n();
  return (
    <div>
      <p className="text-small font-semibold text-brand-strong lg:hidden">
        {t("corpus.wizard.stepOf", { step: current + 1, total: STEPS.length, name: t(`corpus.wizard.steps.${STEPS[current]}`) })}
      </p>
      <div aria-hidden className="mt-2 flex gap-1.5 lg:hidden">
        {STEPS.map((s, i) => (
          <span key={s} className={cn("h-1.5 flex-1 rounded-full", i <= current ? "bg-brand" : "bg-line")} />
        ))}
      </div>
      <ol aria-label={t("corpus.wizard.progress")} className="sticky top-24 hidden flex-col gap-1 lg:flex">
        {STEPS.map((s, i) => {
          const done = i < current;
          const now = i === current;
          return (
            <li
              key={s}
              aria-current={now ? "step" : undefined}
              className={cn(
                "flex min-h-11 items-center gap-3 rounded-md px-3 text-small font-medium",
                now ? "bg-brand-soft text-brand-strong" : done ? "text-ink" : "text-subtle",
              )}
            >
              <span
                className={cn(
                  "grid size-6 shrink-0 place-items-center rounded-full text-caption font-bold",
                  done ? "bg-brand text-white" : now ? "border-2 border-brand text-brand-strong" : "border border-line-strong",
                )}
              >
                {done ? <Check size={13} weight="bold" aria-hidden /> : i + 1}
              </span>
              {t(`corpus.wizard.steps.${s}`)}
              {done ? <span className="sr-only"> — {t("corpus.wizard.done")}</span> : null}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function Panel({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section aria-labelledby="wizard-step" className="flex flex-col gap-5 rounded-md border border-line bg-surface p-5 motion-safe:animate-rise sm:p-6">
      <div>
        <h2 id="wizard-step" className="text-heading text-ink">
          {title}
        </h2>
        {hint ? <p className="mt-1 text-small text-muted">{hint}</p> : null}
      </div>
      {children}
    </section>
  );
}

function Actions({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap gap-2 border-t border-line pt-4">{children}</div>;
}

/** A large target for the PDF, by click or by drop. The input itself is the control. */
function FileDrop({ file, onFile }: { file: File | null; onFile: (file: File | null) => void }) {
  const { t } = useI18n();
  const [over, setOver] = useState(false);
  const drop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    onFile(e.dataTransfer.files?.[0] ?? null);
  };
  return (
    <Field label={t("corpus.upload.file")} hint={t("corpus.wizard.fileHint")}>
      {(p) => (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={drop}
          className={cn(
            "relative flex flex-col items-center gap-2 rounded-md border-2 border-dashed px-4 py-8 text-center transition-colors duration-150",
            over ? "border-brand bg-brand-tint" : "border-line-strong/70 bg-sunken/50",
          )}
        >
          <FilePdf size={32} aria-hidden className="text-brand" />
          {file ? (
            <p className="font-semibold text-ink">
              {file.name} <span className="font-normal text-muted">· {formatBytes(file.size, t)}</span>
            </p>
          ) : (
            <p className="text-small text-muted">{t("corpus.wizard.drop")}</p>
          )}
          <input
            {...p}
            type="file"
            accept="application/pdf,.pdf"
            onChange={(e) => onFile(e.target.files?.[0] ?? null)}
            className="block w-full max-w-sm cursor-pointer text-small file:mr-3 file:min-h-10 file:cursor-pointer file:rounded-md file:border-0 file:bg-brand file:px-4 file:font-semibold file:text-white"
          />
        </div>
      )}
    </Field>
  );
}
