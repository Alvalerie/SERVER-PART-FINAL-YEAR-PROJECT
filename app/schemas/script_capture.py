"""
app/schemas/script_capture.py

Shapes for processing one captured script. The server stores no images
and no capture rows -- it returns a verdict, and the phone keeps
whatever needs review.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SuggestionSource = Literal["ocr_exact", "ocr_fuzzy", "handwriting"]

# written    -> mark was auto-written to the session row, nothing to do
# review     -> needs the lecturer; phone keeps the images and shows them
Verdict = Literal["written", "review"]

# Why a script went to review, so the phone can render the right screen.
ReviewReason = Literal["fuzzy", "not_in_csv", "low_mark", "auto_off"]


class StudentSuggestion(BaseModel):
    student_no: str
    source: SuggestionSource
    # 1.0 exact; fuzzy ratio/100; 1 - cosine distance for handwriting.
    # Not comparable across sources, not a probability. Rank, don't %.
    score: float


class MarkProposal(BaseModel):
    value: float | None = None
    confidence: float = 0.0
    candidates: list[float] = Field(default_factory=list)


class ProcessResult(BaseModel):
    """One processed script.

    client_id echoes the phone's own id for the capture, so the phone
    can match this verdict to the queued item and mark it done or move
    it to review.
    """

    client_id: str
    verdict: Verdict

    # Present when verdict == written.
    student_no: str | None = None
    mark: float | None = None

    # Present when verdict == review.
    reason: ReviewReason | None = None
    suggestions: list[StudentSuggestion] = Field(default_factory=list)
    mark_proposal: MarkProposal | None = None