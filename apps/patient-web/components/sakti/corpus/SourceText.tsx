"use client";

import { useApi } from "@carebridge/api-client/react";
import { errorMessage, useI18n } from "@carebridge/i18n";
import {
  LOCATOR_TYPES,
  type CorpusSourceText,
  type LocatorType,
  type Provision,
  type ProvisionVersionDetail,
} from "@carebridge/shared-types";
import { Alert, Badge, Button, Card, Field, Select, TextInput, cn } from "@carebridge/ui";
import Link from "next/link";
import { useMemo, useState } from "react";
import { pageRange } from "./labels";
import { documentText, linesOf, pagesOfSpan, spanBetween, type Line } from "./span";

const NEW = "__new__";

/**
 * The text of a source as it was read, one page at a time — and, while the
 * source can still take versions, the tool for taking a provision from it.
 *
 * A provision is chosen by its first and last line. Only those two offsets are
 * sent; the server cuts the text from what it stored and returns it. There is
 * no field anyone could type legal text into.
 */
export function SourceText({
  sourceId,
  text,
  provisions,
  instrumentId,
  canMark,
  onCreated,
}: {
  sourceId: string;
  text: CorpusSourceText;
  provisions: Provision[];
  instrumentId: string;
  canMark: boolean;
  onCreated: (version: ProvisionVersionDetail) => void;
}) {
  const { t } = useI18n();
  const [pageIndex, setPageIndex] = useState(0);
  const [anchor, setAnchor] = useState<Line | null>(null);
  const [focus, setFocus] = useState<Line | null>(null);

  const page = text.pages[pageIndex];
  const lines = useMemo(() => (page ? linesOf(page) : []), [page]);
  const span = anchor && focus ? spanBetween(anchor, focus) : null;
  const inSpan = (line: Line) =>
    span ? line.start >= span.start && line.end <= span.end : anchor ? line.start === anchor.start : false;

  function choose(line: Line) {
    if (!anchor || (anchor && focus)) {
      setAnchor(line);
      setFocus(null);
    } else {
      setFocus(line);
    }
  }

  const count = text.pages.length;
  const method = page?.method ?? "none";

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <Field label={t("corpus.source.page")} className="w-44">
          {(p) => (
            <Select {...p} value={pageIndex} onChange={(e) => setPageIndex(Number(e.target.value))}>
              {text.pages.map((pg, i) => (
                <option key={pg.page_number} value={i}>
                  {t("corpus.source.pageOf", { page: pg.page_number, count })}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" disabled={pageIndex === 0} onClick={() => setPageIndex(pageIndex - 1)}>
            {t("corpus.source.previousPage")}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={pageIndex >= count - 1}
            onClick={() => setPageIndex(pageIndex + 1)}
          >
            {t("corpus.source.nextPage")}
          </Button>
        </div>
      </div>

      <p className="flex flex-wrap items-center gap-2 text-small text-muted">
        <Badge tone={method === "ocr" ? "warning" : method === "pdf_text_layer" ? "success" : "neutral"}>
          {t(`corpus.method.${method}`)}
        </Badge>
        {page?.confidence != null ? (
          <span>{t("corpus.method.confidence", { value: Math.round(page.confidence * 100) })}</span>
        ) : null}
        <span className="text-subtle">{page?.engine}</span>
      </p>

      {canMark ? <p className="text-small text-muted">{t("corpus.mark.help")}</p> : null}

      {page && page.text.length === 0 ? (
        <p className="rounded-md border border-dashed border-line px-4 py-6 text-center text-muted">
          {t("corpus.source.emptyPage")}
        </p>
      ) : (
        <ol
          className="max-h-[32rem] overflow-y-auto rounded-md border border-line bg-surface py-2 font-mono text-small leading-relaxed"
        >
          {lines.map((line) => (
            <li
              key={line.start}
              className={cn(
                "grid grid-cols-[3rem_minmax(0,1fr)] items-start gap-2 px-2",
                inSpan(line) && "bg-brand-tint",
              )}
            >
              {canMark ? (
                <button
                  type="button"
                  onClick={() => choose(line)}
                  aria-pressed={inSpan(line)}
                  aria-label={t(anchor && !focus ? "corpus.mark.lineEnd" : "corpus.mark.lineStart", { line: line.number })}
                  className="min-h-7 rounded-sm text-right text-subtle hover:bg-sunken hover:text-ink focus-visible:outline-2 focus-visible:outline-brand"
                >
                  {line.number}
                </button>
              ) : (
                <span aria-hidden className="select-none pt-0.5 text-right text-subtle">
                  {line.number}
                </span>
              )}
              <span className="whitespace-pre-wrap break-words py-0.5 text-ink">{line.text || " "}</span>
            </li>
          ))}
        </ol>
      )}

      {canMark && anchor && !focus ? <p className="text-small font-medium text-ink">{t("corpus.mark.startOnly")}</p> : null}
      {canMark && span ? (
        <MarkForm
          key={`${span.start}-${span.end}`}
          sourceId={sourceId}
          instrumentId={instrumentId}
          provisions={provisions}
          span={span}
          preview={documentText(text.pages).slice(span.start, span.end)}
          pages={pagesOfSpan(text.pages, span)}
          onClear={() => {
            setAnchor(null);
            setFocus(null);
          }}
          onCreated={(version) => {
            setAnchor(null);
            setFocus(null);
            onCreated(version);
          }}
        />
      ) : null}
    </div>
  );
}

function MarkForm({
  sourceId,
  instrumentId,
  provisions,
  span,
  preview,
  pages,
  onClear,
  onCreated,
}: {
  sourceId: string;
  instrumentId: string;
  provisions: Provision[];
  span: { start: number; end: number };
  preview: string;
  pages: { first: number; last: number };
  onClear: () => void;
  onCreated: (version: ProvisionVersionDetail) => void;
}) {
  const api = useApi();
  const { t } = useI18n();
  const [provisionId, setProvisionId] = useState(provisions[0]?.id ?? NEW);
  const [locator, setLocator] = useState("");
  const [locatorType, setLocatorType] = useState<LocatorType>("section");
  const [validFrom, setValidFrom] = useState("");
  const [validTo, setValidTo] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const isNew = provisionId === NEW;

  async function create() {
    setBusy(true);
    setError(null);
    try {
      const target = isNew
        ? (await api.corpus.createProvision(instrumentId, { locator: locator.trim(), locator_type: locatorType })).id
        : provisionId;
      const version = await api.corpus.createVersion(sourceId, {
        provision_id: target,
        char_start: span.start,
        char_end: span.end,
        valid_from: validFrom || null,
        valid_to: validTo || null,
      });
      onCreated(version);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card tone="quiet" aria-labelledby="mark-title">
      <h3 id="mark-title" className="text-subheading text-ink">
        {t("corpus.mark.title")}
      </h3>
      <p className="mt-3 text-small font-semibold text-muted">
        {t("corpus.mark.selectionTitle")} · {pageRange(t, pages.first, pages.last)}
      </p>
      <blockquote className="mt-1 max-h-60 overflow-y-auto whitespace-pre-wrap break-words rounded-md border border-line bg-surface p-3 font-mono text-small text-ink">
        {preview}
      </blockquote>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <Field label={t("corpus.mark.provision")} className="sm:col-span-2">
          {(p) => (
            <Select {...p} value={provisionId} onChange={(e) => setProvisionId(e.target.value)}>
              {provisions.map((pr) => (
                <option key={pr.id} value={pr.id}>
                  {pr.locator} · {t(`corpus.locatorType.${pr.locator_type}`)}
                </option>
              ))}
              <option value={NEW}>{t("corpus.mark.newProvision")}</option>
            </Select>
          )}
        </Field>
        {isNew ? (
          <>
            <Field label={t("corpus.mark.locator")} hint={t("corpus.mark.locatorHint")}>
              {(p) => <TextInput {...p} maxLength={200} value={locator} onChange={(e) => setLocator(e.target.value)} />}
            </Field>
            <Field label={t("corpus.locatorType.label")}>
              {(p) => (
                <Select {...p} value={locatorType} onChange={(e) => setLocatorType(e.target.value as LocatorType)}>
                  {LOCATOR_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {t(`corpus.locatorType.${type}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </>
        ) : null}
        <Field label={t("corpus.mark.validFrom")}>
          {(p) => <TextInput {...p} type="date" value={validFrom} onChange={(e) => setValidFrom(e.target.value)} />}
        </Field>
        <Field label={t("corpus.mark.validTo")}>
          {(p) => <TextInput {...p} type="date" value={validTo} onChange={(e) => setValidTo(e.target.value)} />}
        </Field>
        <p className="text-small text-muted sm:col-span-2">{t("corpus.mark.validityHint")}</p>
      </div>

      {error ? (
        <Alert tone="error" className="mt-4">
          {errorMessage(t, error)}
        </Alert>
      ) : null}
      <div className="mt-4 flex flex-wrap gap-2">
        <Button onClick={create} disabled={busy || (isNew && !locator.trim())}>
          {busy ? t("corpus.mark.creating") : t("corpus.mark.create")}
        </Button>
        <Button variant="ghost" onClick={onClear} disabled={busy}>
          {t("corpus.mark.clear")}
        </Button>
      </div>
    </Card>
  );
}

/** A provision version, as a link. */
export function VersionLink({ id, locator, number }: { id: string; locator: string; number: number }) {
  const { t } = useI18n();
  return (
    <Link href={`/curator/versions/${id}`} className="font-medium text-brand-strong hover:underline">
      {t("corpus.source.versionLink", { locator, number })}
    </Link>
  );
}
