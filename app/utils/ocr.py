"""
app/utils/ocr.py

Read a single field from a cropped image with PaddleOCR.

Crops carry one thing each -- a computer number, or a mark -- so there
is no page furniture to classify against. The number crop reads at high
confidence; the mark crop is a 1-3 digit read, far more reliable
isolated than it ever was on a full page.

The PaddleOCR object holds model weights and is slow to build, so it is
created once and reused.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from paddleocr import PaddleOCR

from .image_io import decode_bgr

COMP_NO_RE = re.compile(r"^20\d{8}$")
DIGITS_RE = re.compile(r"\d+")

_ocr: PaddleOCR | None = None


def _get_ocr() -> PaddleOCR:
    global _ocr
    if _ocr is None:
        # Built on first use, not at import: the model load is slow and
        # must not block app startup or the CSV trunk.
        _ocr = PaddleOCR(lang="en")
    return _ocr


@dataclass
class FieldRead:
    # None means "nothing usable read", not "read as empty".
    text: str | None
    confidence: float
    # Every digit run seen, best-confidence first. The service decides
    # what to do when a crop yields more than one.
    candidates: list[str]


def _read_digit_runs(image_bytes: bytes) -> list[tuple[str, float]]:
    """All digit runs across all recognised lines, with the line's
    confidence, best first."""
    image = decode_bgr(image_bytes)
    result = _get_ocr().predict(image)

    runs: list[tuple[str, float]] = []
    for res in result:
        data = res.json.get("res", res.json) if hasattr(res, "json") else res
        texts = data.get("rec_texts", [])
        scores = data.get("rec_scores", [])
        for text, score in zip(texts, scores):
            for run in DIGITS_RE.findall(str(text)):
                runs.append((run, float(score)))

    runs.sort(key=lambda r: r[1], reverse=True)
    return runs


def read_computer_number(image_bytes: bytes) -> FieldRead:
    """Pick the highest-confidence 10-digit run beginning with 20."""
    runs = _read_digit_runs(image_bytes)
    valid = [(r, c) for r, c in runs if COMP_NO_RE.match(r)]

    if not valid:
        # Surface whatever WAS read, so the review screen can show the
        # lecturer why the crop failed rather than a bare "no number".
        return FieldRead(
            text=None,
            confidence=0.0,
            candidates=[r for r, _ in runs],
        )

    best_text, best_conf = valid[0]
    return FieldRead(
        text=best_text,
        confidence=best_conf,
        candidates=[r for r, _ in valid],
    )


def read_mark(image_bytes: bytes, max_mark: float) -> FieldRead:
    """Pick the highest-confidence 1-3 digit run within the paper's
    maximum. Multiple survivors are returned for the lecturer to pick."""
    runs = _read_digit_runs(image_bytes)

    valid: list[tuple[str, float]] = []
    for run, conf in runs:
        if 1 <= len(run) <= 3 and 0 <= float(run) <= max_mark:
            valid.append((run, conf))

    if not valid:
        return FieldRead(text=None, confidence=0.0, candidates=[])

    best_text, best_conf = valid[0]
    return FieldRead(
        text=best_text,
        confidence=best_conf,
        candidates=[r for r, _ in valid],
    )