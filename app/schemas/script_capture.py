"""
app/schemas/script_capture.py

Request/response shapes for the capture flow.

Everything here is a PROPOSAL. A capture never asserts who a script
belongs to; it offers candidates and a suggested mark, and the lecturer
confirms via set_mark. The one exception is auto_confirm_exact.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Where a student suggestion came from -- also the evidence for how often
# each path actually worked, which is a result worth reporting.
SuggestionSource = Literal["ocr_exact", "ocr_fuzzy", "handwriting"]

# The capture's resolution state after number matching.
CaptureStatus = Literal["matched", "fuzzy", "not_in_csv", "confirmed"]


class StudentSuggestion(BaseModel):
    student_no: str
    source: SuggestionSource

    # 1.0 for an exact match. For fuzzy, the RapidFuzz ratio /100. For
    # handwriting, 1 - cosine distance. NOT comparable across sources and
    # NOT a probability -- the UI must not render it as a confidence %.
    score: float


class MarkProposal(BaseModel):
    # None means the mark crop read nothing usable. The lecturer types it.
    value: float | None = None
    confidence: float = 0.0

    # Every plausible mark the crop yielded, best first. More than one
    # means the lecturer picks; the system does not guess.
    candidates: list[float] = Field(default_factory=list)


class CaptureProposal(BaseModel):
    """
    Returned right after the three crops are uploaded.

    status tells the app what to render:
      matched     -> one exact student, confirm the (pre-filled) mark
      fuzzy       -> ranked OCR near-matches, lecturer picks
      not_in_csv  -> number failed; handwriting suggestions instead
      confirmed   -> auto_confirm_exact fired; mark already written
    """

    capture_id: int
    status: CaptureStatus

    ocr_number: str | None = None
    number_confidence: float = 0.0

    suggestions: list[StudentSuggestion] = Field(default_factory=list)
    mark: MarkProposal

    # True only when the session toggle is on AND the number matched
    # exactly AND the mark read cleared its confidence bar. Almost always
    # false, by design.
    auto_confirmed: bool = False


class CaptureOut(BaseModel):
    """A stored capture, for the review list and single-capture reads."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int

    number_path: str
    mark_path: str
    handwriting_path: str

    ocr_number: str | None = None
    ocr_number_conf: float | None = None
    ocr_mark: str | None = None
    ocr_mark_conf: float | None = None

    resolved_student_no: str | None = None
    match_method: str | None = None
    status: str

    captured_by: int
    captured_at: datetime