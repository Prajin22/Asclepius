"""Read an uploaded medical document into per-page text with provenance.

PDF pages with an embedded text layer are copied exactly. Pages without one
(scans) and image uploads go to OCR. Nothing here interprets medical meaning.
"""

import io
from dataclasses import dataclass

import pdfplumber

from app.providers.documents.base import (
    METHOD_NONE,
    METHOD_OCR,
    METHOD_TEXT_LAYER,
    METHOD_VISION,
    DocumentReadError,
    DocumentReadResult,
    DocumentTooLarge,
    DocumentUnsupported,
    OcrEngine,
    OcrUnavailable,
    PageText,
    TextBlock,
    union_bbox,
)
from app.providers.documents.ocr import RapidOcrEngine, ocr_available
from app.providers.documents.pdf_text import read_text_layer_page
from app.providers.documents.render import load_image, pdf_page_count, render_pdf_page

PDF_MIME = "application/pdf"
IMAGE_MIMES = frozenset({"image/jpeg", "image/png", "image/webp"})


@dataclass(frozen=True)
class ReadOptions:
    max_pages: int = 10
    # A PDF page with fewer embedded characters than this is treated as a scan.
    min_text_layer_chars: int = 20
    render_scale: float = 2.0
    max_pixels: int = 40_000_000


_local_engine: RapidOcrEngine | None = None


def local_ocr_engine() -> OcrEngine | None:
    """The offline engine, or None when it is not installed."""
    global _local_engine
    if not ocr_available():
        return None
    if _local_engine is None:
        _local_engine = RapidOcrEngine()
    return _local_engine


def read_document(
    data: bytes, mime_type: str, options: ReadOptions, ocr: OcrEngine | None
) -> DocumentReadResult:
    if mime_type == PDF_MIME:
        return _read_pdf(data, options, ocr)
    if mime_type in IMAGE_MIMES:
        if ocr is None:
            raise OcrUnavailable("No OCR engine is available to read images")
        image = load_image(data, max_pixels=options.max_pixels)
        return DocumentReadResult(pages=[ocr.read(image, 1)], page_count=1)
    raise DocumentUnsupported(f"Documents of type {mime_type} cannot be read")


def _read_pdf(data: bytes, options: ReadOptions, ocr: OcrEngine | None) -> DocumentReadResult:
    total = pdf_page_count(data)
    if total == 0:
        raise DocumentReadError("The PDF has no pages")
    count = min(total, max(1, options.max_pages))

    pages: list[PageText] = []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for index in range(count):
                layer = read_text_layer_page(pdf.pages[index], index + 1)
                if len(layer.text.strip()) >= options.min_text_layer_chars:
                    pages.append(layer)
                    continue
                if ocr is None:
                    layer.warnings.append("no_text_layer_and_ocr_unavailable")
                    pages.append(layer)
                    continue
                image = render_pdf_page(data, index, scale=options.render_scale, max_pixels=options.max_pixels)
                pages.append(ocr.read(image, index + 1))
    except DocumentReadError:
        raise
    except Exception as exc:  # malformed PDFs raise many parser-specific errors
        raise DocumentReadError("The PDF could not be read") from exc

    warnings = [f"only_first_{count}_of_{total}_pages_processed"] if total > count else []
    return DocumentReadResult(pages=pages, page_count=total, truncated=total > count, warnings=warnings)


__all__ = [
    "IMAGE_MIMES",
    "METHOD_NONE",
    "METHOD_OCR",
    "METHOD_TEXT_LAYER",
    "METHOD_VISION",
    "PDF_MIME",
    "DocumentReadError",
    "DocumentReadResult",
    "DocumentTooLarge",
    "DocumentUnsupported",
    "OcrEngine",
    "OcrUnavailable",
    "PageText",
    "ReadOptions",
    "TextBlock",
    "local_ocr_engine",
    "read_document",
    "union_bbox",
]
