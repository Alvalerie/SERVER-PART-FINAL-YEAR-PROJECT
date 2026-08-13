"""
app/services/marking_session.py

A marking session is one uploaded CSV being worked through.

The CSV is transient working state, not a permanent record of results:
it is imported, filled in as scripts are captured, exported, and can
then be deleted. Storing results in a school database is out of scope --
the CSV is the deliverable.
"""

from __future__ import annotations

import csv
import io
import json
import logging

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..repositories.handwriting_sample import HandwritingSampleRepository
from ..repositories.marking_session import MarkingSessionRepository
from ..schemas.marking_session import (
    SessionImportResult,
    SessionOut,
    SessionProgress,
)
from ..utils.csv_roster import CsvParseError, parse_roster

logger = logging.getLogger(__name__)

ALLOWED_CSV_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",   # what Windows often reports for .csv
    "text/plain",
}


class MarkingSessionService:

    def __init__(self, db: Session) -> None:
        self.repo = MarkingSessionRepository(db)
        self.samples = HandwritingSampleRepository(db)

    # -----------------------------------------------------------------
    # Import
    # -----------------------------------------------------------------

    async def create_from_csv(
        self,
        label: str,
        max_mark: float,
        file: UploadFile,
        user_id: int,
    ) -> SessionImportResult:
        """
        Parse the CSV and create the session plus one row per student.

        Returns everything the lecturer needs to know BEFORE they start
        marking: rows skipped, and how many students can actually be
        suggested by the handwriting fallback. Discovering mid-session
        that a third of the class was never enrolled is far worse than
        being told now.
        """
        if file.content_type not in ALLOWED_CSV_TYPES:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Expected a CSV file, got '{file.content_type}'.",
            )

        contents = await file.read()

        try:
            roster = parse_roster(contents, max_mark=max_mark)
        except CsvParseError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "CSV_UNUSABLE", "message": str(exc)},
            )

        session = self.repo.create_session(
            label=label,
            max_mark=max_mark,
            csv_filename=file.filename,
            # Original header text in original order. Export replays this
            # so the lecturer gets their own layout back.
            csv_columns=json.dumps(roster.columns),
            comp_no_column=roster.comp_no_column,
            mark_column=roster.mark_column,
            created_by=user_id,
        )

        self.repo.bulk_create_rows(session.id, roster.rows)

        # Coverage: which of these students could the handwriting
        # fallback actually suggest?
        student_nos = [r.student_no for r in roster.rows]
        counts = self.samples.counts_for_students(student_nos)
        enrolled = [no for no, n in counts.items() if n >= self._min_samples()]

        return SessionImportResult(
            session=SessionOut.model_validate(session),
            rows_imported=len(roster.rows),
            comp_no_column=roster.comp_no_column,
            mark_column=roster.mark_column,
            warnings=roster.warnings,
            students_enrolled=len(enrolled),
            students_not_enrolled=len(student_nos) - len(enrolled),
            not_enrolled_student_nos=sorted(
                set(student_nos) - set(enrolled)
            )[:50],
        )

    @staticmethod
    def _min_samples() -> int:
        from ..config.settings import settings
        return settings.MIN_SAMPLES_PER_STUDENT

    # -----------------------------------------------------------------
    # Progress
    # -----------------------------------------------------------------

    def get_progress(self, session_id: int) -> SessionProgress:
        session = self._get_or_404(session_id)
        total = self.repo.count_rows(session.id)
        marked = self.repo.count_marked_rows(session.id)

        return SessionProgress(
            session_id=session.id,
            label=session.label,
            total_rows=total,
            marked_rows=marked,
            remaining_rows=total - marked,
            is_complete=total > 0 and marked == total,
        )

    def roster_student_nos(self, session_id: int) -> list[str]:
        """
        The candidate pool for identification.

        Narrowing the handwriting search from every enrolled student to
        the students on this one roster is the largest accuracy gain
        available, and it costs nothing at the model level.
        """
        self._get_or_404(session_id)
        return self.repo.list_student_nos(session_id)

    # -----------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------

    def export_csv(self, session_id: int) -> tuple[str, str]:
        """
        Rebuild the lecturer's CSV with the marks filled in.

        Returns (csv_text, filename).

        The round trip is the contract: importing a file and exporting it
        immediately, with nothing marked, must give back the original
        content. That is worth an actual test -- it is the only thing
        proving `extra` and `csv_columns` are preserving the layout.
        """
        session = self._get_or_404(session_id)
        rows = self.repo.list_rows(session.id)

        columns: list[str] = json.loads(session.csv_columns)

        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()

        for row in rows:
            record = dict(row.extra or {})
            record[session.comp_no_column] = row.student_no
            # Blank, not 0, for an unmarked script. A zero is a mark
            # somebody earned; an empty cell is a script not yet seen,
            # and conflating them would silently fail students.
            record[session.mark_column] = (
                _format_mark(row.mark) if row.mark is not None else ""
            )
            writer.writerow(record)

        self.repo.mark_exported(session)

        base = (session.csv_filename or session.label).rsplit(".", 1)[0]
        return buffer.getvalue(), f"{base}_marked.csv"

    # -----------------------------------------------------------------
    # Rows
    # -----------------------------------------------------------------

    def set_mark(
        self,
        session_id: int,
        student_no: str,
        mark: Decimal,
        match_method: str,
        user_id: int,
        script_path: str | None = None,
    ):
        """
        Record a confirmed mark.

        Always called by a human confirming, never by OCR directly --
        the extraction proposes, the lecturer decides.
        """
        session = self._get_or_404(session_id)

        if not 0 <= mark <= float(session.max_mark):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "MARK_OUT_OF_RANGE",
                    "message": f"Mark must be between 0 and {session.max_mark:g}.",
                },
            )

        row = self.repo.get_row(session_id, student_no)
        if row is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"{student_no} is not on this session's roster.",
            )

        if row.mark is not None:
            logger.info(
                "mark overwritten session=%s student=%s old=%s new=%s user=%s",
                session_id, student_no, row.mark, mark, user_id,
            )

        return self.repo.set_mark(
            row,
            mark=mark,
            match_method=match_method,
            marked_by=user_id,
            script_path=script_path,
        )

    # -----------------------------------------------------------------

    def _get_or_404(self, session_id: int):
        session = self.repo.get_session(session_id)
        if session is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"Marking session {session_id} not found.",
            )
        return session


def _format_mark(mark) -> str:
    """40.0 -> '40', 40.5 -> '40.5'. Whole marks should not gain a '.0'
    in a file the lecturer will open in Excel."""
    value = float(mark)
    return str(int(value)) if value.is_integer() else str(value)

def list_sessions(self, user_id: int | None = None) -> list[SessionOut]:
        sessions = self.repo.list_sessions(created_by=user_id)
        return [SessionOut.model_validate(s) for s in sessions]

def list_rows(self, session_id: int, unmarked_only: bool = False):
    self._get_or_404(session_id)
    return (
        self.repo.list_unmarked(session_id)
        if unmarked_only
        else self.repo.list_rows(session_id)
    )

def clear_mark(self, session_id: int, student_no: str):
    self._get_or_404(session_id)
    row = self.repo.get_row(session_id, student_no)
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"{student_no} is not on this session's roster.",
        )
    return self.repo.clear_mark(row)

def delete_session(self, session_id: int) -> None:
    self.repo.delete_session(self._get_or_404(session_id))