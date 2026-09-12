"""Reading documents: exact text layers, OCR for scans and images, page geometry."""

import pytest

from app import synthetic_documents as sd
from app.providers.documents import (
    METHOD_OCR,
    METHOD_TEXT_LAYER,
    DocumentReadError,
    DocumentTooLarge,
    DocumentUnsupported,
    OcrUnavailable,
    ReadOptions,
    local_ocr_engine,
    read_document,
)
from app.services.evidence import canonical

needs_ocr = pytest.mark.skipif(local_ocr_engine() is None, reason="offline OCR engine not installed")


def squashed(text: str) -> str:
    """OCR sometimes drops spaces; compare without them."""
    return canonical(text).replace(" ", "")


def lab_report():
    return read_document(sd.text_pdf(sd.LAB_REPORT), "application/pdf", ReadOptions(), ocr=None)


# ---------- text layer ----------


def test_text_layer_pdf_is_read_exactly_page_by_page():
    result = lab_report()
    assert result.page_count == 2 and not result.truncated
    assert [p.page_number for p in result.pages] == [1, 2]
    assert all(p.method == METHOD_TEXT_LAYER for p in result.pages)
    assert all(p.confidence is None for p in result.pages)  # exact, not estimated
    assert "Total cholesterol: 212 mg/dL" in result.pages[0].text
    assert "Blood pressure: 148/94 mmHg" in result.pages[1].text
    assert "Blood pressure" not in result.pages[0].text  # page provenance is precise


def test_every_line_has_exact_offsets_and_a_position():
    page = lab_report().pages[0]
    assert page.blocks
    for block in page.blocks:
        assert page.text[block.char_start : block.char_end] == block.text
        x0, y0, x1, y1 = block.bbox
        assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1
    tops = [block.bbox[1] for block in page.blocks]
    assert tops == sorted(tops)  # reading order, top to bottom


def test_a_quote_maps_to_the_line_it_came_from():
    page = lab_report().pages[0]
    quote = "212 mg/dL"
    start = page.text.index(quote)
    line = next(b for b in page.blocks if "Total cholesterol" in b.text)
    assert page.bbox_for_span(start, start + len(quote)) == line.bbox
    assert page.bbox_for_span(None, None) is None


# ---------- OCR ----------


@needs_ocr
def test_scanned_pdf_without_a_text_layer_goes_to_ocr():
    result = read_document(sd.scanned_pdf(sd.SCANNED_LAB), "application/pdf", ReadOptions(), local_ocr_engine())
    page = result.pages[0]
    assert page.method == METHOD_OCR
    assert page.engine.startswith("rapidocr-onnxruntime")
    assert page.confidence is not None and page.confidence > 0.8
    assert "hemoglobin" in squashed(page.text)
    assert "150/95" in page.text
    for block in page.blocks:
        assert page.text[block.char_start : block.char_end] == block.text
        assert block.confidence is not None
        assert 0 <= block.bbox[0] < block.bbox[2] <= 1


@needs_ocr
def test_image_upload_is_read_by_ocr():
    result = read_document(sd.png_of_lines(sd.PRESCRIPTION_PHOTO), "image/png", ReadOptions(), local_ocr_engine())
    assert result.page_count == 1
    assert "paracetamol" in squashed(result.pages[0].text)


def test_scan_without_ocr_is_reported_not_guessed():
    result = read_document(sd.scanned_pdf(sd.SCANNED_LAB), "application/pdf", ReadOptions(), ocr=None)
    page = result.pages[0]
    assert page.text == ""
    assert "no_text_layer_and_ocr_unavailable" in page.warnings


def test_image_without_ocr_is_refused():
    with pytest.raises(OcrUnavailable):
        read_document(sd.png_of_lines(["x"]), "image/png", ReadOptions(), ocr=None)


# ---------- limits and bad input ----------


def test_page_limit_truncates_and_says_so():
    pdf = sd.text_pdf([[f"Page {n} has enough text to count as a text layer"] for n in range(1, 4)])
    result = read_document(pdf, "application/pdf", ReadOptions(max_pages=2), ocr=None)
    assert result.page_count == 3
    assert len(result.pages) == 2
    assert result.truncated and result.warnings


def test_corrupt_pdf_is_a_read_error():
    with pytest.raises(DocumentReadError):
        read_document(b"%PDF-1.4\nnot really a pdf", "application/pdf", ReadOptions(), ocr=None)


def test_unsupported_type_is_refused():
    with pytest.raises(DocumentUnsupported):
        read_document(b"hello", "text/plain", ReadOptions(), ocr=None)


def test_oversized_image_is_refused_before_decoding():
    class NeverCalled:
        name, version = "never", "0"

        def read(self, image, page_number):
            raise AssertionError("should not be reached")

    with pytest.raises(DocumentTooLarge):
        read_document(sd.png_of_lines(["x"]), "image/png", ReadOptions(max_pixels=1_000), NeverCalled())
