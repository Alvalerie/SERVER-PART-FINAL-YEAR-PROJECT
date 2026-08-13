"""
app/schemas/marking_session.py

Request/response shapes for marking sessions.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# How a mark came to be recorded. Kept as a closed set because it is
# also the evidence for how often each path actually worked -- which is
# a result worth reporting, not just a housekeeping field.
MatchMethod = Literal["ocr_exact", "ocr_fuzzy", "handwriting", "manual"]


# ---------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------

class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    max_mark: Decimal
    csv_filename: str | None = None
    created_by: int
    created_at: datetime
    exported_at: datetime | None = None


class SessionImportResult(BaseModel):
    """
    Returned after a CSV upload.

    A briefing rather than a receipt: everything the lecturer should
    know before they start capturing scripts.
    """

    session: SessionOut

    rows_imported: int

    # Which headers were detected as the number and the mark. Surfaced
    # so a wrong guess is caught immediately, rather than discovered at
    # export when the file comes back mangled.
    comp_no_column: str
    mark_column: str

    # Rows skipped, marks cleared, a marks column added. Non-fatal, but
    # the lecturer should see them.
    warnings: list[str] = Field(default_factory=list)

    # Handwriting fallback coverage. A student with no enrolled samples
    # can never be suggested, so a low number here means the fallback
    # will mostly come up empty for this class.
    students_enrolled: int
    students_not_enrolled: int

    # Capped, because a class with nobody enrolled would otherwise
    # return the entire roster in an error-ish field.
    not_enrolled_student_nos: list[str] = Field(default_factory=list)


class SessionProgress(BaseModel):
    session_id: int
    label: str
    total_rows: int
    marked_rows: int
    remaining_rows: int
    is_complete: bool


# ---------------------------------------------------------------------
# Rows
# ---------------------------------------------------------------------

class SessionRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    student_no: str
    csv_name: str | None = None
    row_order: int

    # None means "not yet marked", NOT zero. A zero is a mark somebody
    # earned; an empty cell is a script nobody has seen. Conflating them
    # would silently fail students, so the distinction is preserved all
    # the way out to the client.
    mark: Decimal | None = None

    match_method: str | None = None
    script_path: str | None = None
    marked_at: datetime | None = None
    marked_by: int | None = None

    # The lecturer's other columns, verbatim.
    extra: dict = Field(default_factory=dict)


class SetMarkRequest(BaseModel):
    """
    Body for PATCH /sessions/{id}/rows/{student_no}.

    Always a human confirming. OCR and handwriting identification
    propose; this is where a decision gets recorded.
    """

    # Upper bound is not fixed here: it is the session's max_mark, which
    # the service checks. A ge=0 floor is safe for every paper.
    mark: Decimal = Field(ge=0)

    match_method: MatchMethod = Field(
        description="How the student was identified: exact OCR match, "
                    "fuzzy OCR match, handwriting suggestion, or typed "
                    "manually by the lecturer."
    )

    # Set when a captured script image was saved for this row, so the
    # mark can be traced back to the page it came from.
    script_path: str | None = None