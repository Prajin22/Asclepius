"""Exact text from a PDF's embedded text layer (no OCR, no guessing)."""

import importlib.metadata

from app.providers.documents.base import METHOD_TEXT_LAYER, PageText, TextBlock, normalised_bbox

ENGINE = f"pdfplumber {importlib.metadata.version('pdfplumber')}"


def read_text_layer_page(page, page_number: int) -> PageText:
    """Lines in reading order, each with its position and offsets into the page text."""
    width, height = float(page.width), float(page.height)
    lines = page.extract_text_lines(layout=False, strip=True, return_chars=False)

    parts: list[str] = []
    blocks: list[TextBlock] = []
    cursor = 0
    for line in lines:
        text = (line.get("text") or "").strip()
        if not text:
            continue
        start, end = cursor, cursor + len(text)
        blocks.append(
            TextBlock(
                text=text,
                bbox=normalised_bbox(line["x0"], line["top"], line["x1"], line["bottom"], width, height),
                char_start=start,
                char_end=end,
            )
        )
        parts.append(text)
        cursor = end + 1  # the newline joining lines

    return PageText(
        page_number=page_number,
        text="\n".join(parts),
        width=width,
        height=height,
        method=METHOD_TEXT_LAYER,
        engine=ENGINE,
        confidence=None,  # embedded text is exact
        blocks=blocks,
    )
