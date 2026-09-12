"""Offline OCR with RapidOCR (PP-OCRv4 models bundled in the package).

Runs entirely on this machine — no model download, no network — so it works in
DEMO_MODE. The bundled models read printed English (and Chinese). They do not
read Tamil, Hindi or other Indic scripts; those scans need the vision-provider
path, and pages the engine cannot read are reported as such rather than guessed.
"""

import importlib.metadata
import threading

from app.providers.documents.base import METHOD_OCR, PageText, TextBlock, normalised_bbox

LOW_CONFIDENCE = 0.80

_engine = None
_lock = threading.Lock()  # one shared model; inference is serialised


def ocr_available() -> bool:
    try:
        import rapidocr_onnxruntime  # noqa: F401
    except Exception:  # pragma: no cover - depends on the environment
        return False
    return True


class RapidOcrEngine:
    name = "rapidocr-onnxruntime"

    def __init__(self) -> None:
        version = importlib.metadata.version("rapidocr-onnxruntime")
        self.version = f"{self.name} {version} (PP-OCRv4, bundled English/Chinese models)"

    @staticmethod
    def _model():
        global _engine
        if _engine is None:
            from rapidocr_onnxruntime import RapidOCR

            _engine = RapidOCR()
        return _engine

    def read(self, image, page_number: int) -> PageText:
        import numpy as np

        width, height = image.size
        with _lock:
            result, _elapsed = self._model()(np.array(image.convert("RGB")))

        items = []
        for box, text, confidence in result or []:
            xs = [float(point[0]) for point in box]
            ys = [float(point[1]) for point in box]
            items.append((min(ys), min(xs), max(xs), max(ys), str(text).strip(), float(confidence)))
        # Reading order: rows (2% of page height) top to bottom, then left to right.
        items.sort(key=lambda item: (round(item[0] / max(height, 1) * 50), item[1]))

        parts: list[str] = []
        blocks: list[TextBlock] = []
        confidences: list[float] = []
        cursor = 0
        for top, left, right, bottom, text, confidence in items:
            if not text:
                continue
            start, end = cursor, cursor + len(text)
            blocks.append(
                TextBlock(
                    text=text,
                    bbox=normalised_bbox(left, top, right, bottom, width, height),
                    char_start=start,
                    char_end=end,
                    confidence=round(confidence, 4),
                )
            )
            parts.append(text)
            confidences.append(confidence)
            cursor = end + 1

        mean = round(sum(confidences) / len(confidences), 4) if confidences else None
        warnings: list[str] = []
        if not parts:
            warnings.append("no_text_detected")
        elif mean is not None and mean < LOW_CONFIDENCE:
            warnings.append("low_ocr_confidence")

        return PageText(
            page_number=page_number,
            text="\n".join(parts),
            width=float(width),
            height=float(height),
            method=METHOD_OCR,
            engine=self.version,
            confidence=mean,
            blocks=blocks,
            warnings=warnings,
        )
