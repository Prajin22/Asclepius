/**
 * Line and span arithmetic over a source's text, exactly as the server measures it.
 *
 * The document text is every page's text joined by a form feed (U+000C); offsets
 * count UTF-16 code units, as both JavaScript and the API's Python `str` slicing
 * of BMP text do. This module only decides *which* offsets the curator chose. The
 * text itself is always cut by the server from what it stored — the preview here
 * is for the curator's eyes, never sent back.
 */
import type { CorpusPageText } from "@carebridge/shared-types";

export const PAGE_SEPARATOR = "\f";

export interface Line {
  /** 1-based within its page. */
  number: number;
  page: number;
  /** Offsets in the document text. */
  start: number;
  end: number;
  text: string;
}

/** The lines of one page, with document offsets. Blank lines are kept, so numbering matches the source. */
export function linesOf(page: CorpusPageText): Line[] {
  const lines: Line[] = [];
  let position = 0;
  page.text.split("\n").forEach((text, index) => {
    lines.push({
      number: index + 1,
      page: page.page_number,
      start: page.char_start + position,
      end: page.char_start + position + text.length,
      text,
    });
    position += text.length + 1;
  });
  return lines;
}

export interface Span {
  start: number;
  end: number;
}

/** The span from the start of one line to the end of another, whichever order they were chosen in. */
export function spanBetween(a: Line, b: Line): Span {
  const [first, last] = a.start <= b.start ? [a, b] : [b, a];
  return { start: first.start, end: last.end };
}

/** The document text, rebuilt exactly as the server builds it. */
export function documentText(pages: CorpusPageText[]): string {
  return pages.map((p) => p.text).join(PAGE_SEPARATOR);
}

/** The first and last page a span touches. */
export function pagesOfSpan(pages: CorpusPageText[], span: Span): { first: number; last: number } {
  let first = pages[0]?.page_number ?? 1;
  let last = first;
  for (const page of pages) {
    if (page.char_start <= span.start) first = page.page_number;
    if (page.char_start < span.end) last = page.page_number;
  }
  return { first, last: Math.max(first, last) };
}
