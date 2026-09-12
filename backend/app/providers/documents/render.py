"""Rasterising PDF pages and loading images, with limits for untrusted input."""

import io

import pypdfium2 as pdfium
from PIL import Image, ImageOps

from app.providers.documents.base import DocumentReadError, DocumentTooLarge

# Decompression-bomb guard for untrusted images and renders (width × height).
DEFAULT_MAX_PIXELS = 40_000_000


def _open_pdf(data: bytes) -> pdfium.PdfDocument:
    try:
        return pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        raise DocumentReadError("The PDF could not be opened") from exc


def pdf_page_count(data: bytes) -> int:
    pdf = _open_pdf(data)
    try:
        return len(pdf)
    finally:
        pdf.close()


def pdf_page_size(data: bytes, page_index: int) -> tuple[float, float]:
    pdf = _open_pdf(data)
    try:
        page = pdf[page_index]
        try:
            width, height = page.get_size()
            return float(width), float(height)
        finally:
            page.close()
    finally:
        pdf.close()


def render_pdf_page(
    data: bytes, page_index: int, *, scale: float = 2.0, max_pixels: int = DEFAULT_MAX_PIXELS
) -> Image.Image:
    """Render one page to RGB, lowering the scale if it would exceed `max_pixels`."""
    pdf = _open_pdf(data)
    try:
        if page_index < 0 or page_index >= len(pdf):
            raise DocumentReadError("Page does not exist")
        page = pdf[page_index]
        try:
            width, height = page.get_size()
            if width * height <= 0:
                raise DocumentReadError("Page has no area")
            if width * scale * height * scale > max_pixels:
                scale = (max_pixels / (width * height)) ** 0.5
            bitmap = page.render(scale=scale)
            try:
                return bitmap.to_pil().convert("RGB")
            finally:
                bitmap.close()
        finally:
            page.close()
    finally:
        pdf.close()


def load_image(data: bytes, *, max_pixels: int = DEFAULT_MAX_PIXELS) -> Image.Image:
    """Decode an uploaded image, honouring EXIF rotation, refusing oversized ones."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > max_pixels:
                raise DocumentTooLarge("The image is too large to process")
            upright = ImageOps.exif_transpose(image)
            return upright.convert("RGB")
    except DocumentTooLarge:
        raise
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise DocumentReadError("The image could not be read") from exc


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
