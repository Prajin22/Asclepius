"""Document reading contract: bytes in, per-page text with geometry out.

Reading is not interpretation. A PDF text layer is copied exactly as the file
contains it; OCR transcribes what an image shows and can be wrong. Every page
therefore records *how* its text was obtained (method, engine, confidence), and
every line keeps its position on the page, so any later fact can be traced to
the exact place it came from. Structured extraction happens afterwards, in the
AI pipeline, against this text — never against the reader's own guesses.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol

METHOD_TEXT_LAYER = "pdf_text_layer"  # exact text embedded in the PDF
METHOD_OCR = "ocr"  # machine transcription of an image, local engine
METHOD_VISION = "vision_provider"  # machine transcription by an external AI provider
METHOD_NONE = "none"  # nothing could be read from this page

BBox = tuple[float, float, float, float]  # x0, y0, x1, y1 as fractions of the page, origin top-left


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def normalised_bbox(x0: float, y0: float, x1: float, y1: float, width: float, height: float) -> BBox:
    width = width or 1.0
    height = height or 1.0
    return (
        round(_clamp(x0 / width), 5),
        round(_clamp(y0 / height), 5),
        round(_clamp(x1 / width), 5),
        round(_clamp(y1 / height), 5),
    )


def union_bbox(boxes: Iterable[BBox]) -> BBox | None:
    boxes = list(boxes)
    if not boxes:
        return None
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


@dataclass(frozen=True)
class TextBlock:
    """One line of text and where it sits on the page."""

    text: str
    bbox: BBox
    char_start: int  # offsets into PageText.text
    char_end: int
    confidence: float | None = None

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "bbox": list(self.bbox),
            "char_start": self.char_start,
            "char_end": self.char_end,
            "confidence": self.confidence,
        }


@dataclass
class PageText:
    page_number: int  # 1-based
    text: str
    width: float
    height: float
    method: str
    engine: str
    confidence: float | None = None  # mean OCR confidence; None when the text is exact
    blocks: list[TextBlock] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def bbox_for_span(self, start: int | None, end: int | None) -> BBox | None:
        """Region covering the lines that a character span touches."""
        if start is None or end is None or end <= start:
            return None
        return union_bbox(b.bbox for b in self.blocks if b.char_start < end and b.char_end > start)


@dataclass
class DocumentReadResult:
    pages: list[PageText]
    page_count: int  # pages in the file
    truncated: bool = False  # more pages than were processed
    warnings: list[str] = field(default_factory=list)


class DocumentReadError(Exception):
    code = "document_unreadable"

    def __init__(self, message: str = ""):
        super().__init__(message or self.code)
        self.message = message or self.code


class DocumentUnsupported(DocumentReadError):
    code = "document_unsupported"


class OcrUnavailable(DocumentReadError):
    code = "ocr_unavailable"


class DocumentTooLarge(DocumentReadError):
    code = "document_too_large"


class OcrEngine(Protocol):
    """Local image-to-text engine. Must never call the network."""

    name: str
    version: str

    def read(self, image, page_number: int) -> PageText: ...
