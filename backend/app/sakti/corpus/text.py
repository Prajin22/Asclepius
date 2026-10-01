"""The document text, its chunks and its spans. Pure functions, no I/O.

A source document's text is every page's text, exactly as read, in page order,
joined by a form feed (U+000C). The form feed marks a page break and nothing
else; no other character is added, removed or changed. Every offset in the
corpus — a page's start, a chunk, a provision version's span — is measured in
this one string, so any stored slice can be checked against the pages it came
from.
"""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

PAGE_SEPARATOR = "\f"
#: A chunk grows line by line up to this many characters, never past a page.
CHUNK_MAX_CHARS = 1200


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def assemble(page_texts: Sequence[str]) -> tuple[str, list[int]]:
    """The document text, and where each page starts in it."""
    starts: list[int] = []
    offset = 0
    for text in page_texts:
        starts.append(offset)
        offset += len(text) + len(PAGE_SEPARATOR)
    return PAGE_SEPARATOR.join(page_texts), starts


@dataclass(frozen=True)
class ChunkSpan:
    ordinal: int
    page_number: int
    char_start: int  # in the document text
    char_end: int


def chunk_pages(pages: Sequence[tuple[int, int, str]], max_chars: int = CHUNK_MAX_CHARS) -> list[ChunkSpan]:
    """Split (page_number, page_start, page_text) into line-bounded chunks.

    Consecutive lines of one page are grouped until the next line would take
    the chunk past `max_chars`. A line is never split, so a single line longer
    than the limit is a chunk of its own. Blank lines never start a chunk. The
    same pages always give the same chunks.
    """
    chunks: list[ChunkSpan] = []
    for page_number, page_start, text in pages:
        start: int | None = None
        end = 0
        position = 0
        for line in text.split("\n"):
            line_start, line_end = position, position + len(line)
            position = line_end + 1
            if start is None:
                if not line.strip():
                    continue
                start = line_start
            elif line.strip() and line_end - start > max_chars:
                chunks.append(ChunkSpan(len(chunks), page_number, page_start + start, page_start + end))
                start = line_start
            if line.strip():
                end = line_end
        if start is not None:
            chunks.append(ChunkSpan(len(chunks), page_number, page_start + start, page_start + end))
    return chunks


def pages_of_span(page_starts: Sequence[int], page_lengths: Sequence[int], start: int, end: int) -> tuple[int, int]:
    """The first and last page (1-based) a span [start, end) touches."""
    first = last = None
    for index, (page_start, length) in enumerate(zip(page_starts, page_lengths, strict=True)):
        page_end = page_start + length
        if first is None and start < page_end + len(PAGE_SEPARATOR):
            first = index + 1
        if page_start < end:
            last = index + 1
    if first is None or last is None:
        raise ValueError("span is outside the document")
    return first, max(first, last)
