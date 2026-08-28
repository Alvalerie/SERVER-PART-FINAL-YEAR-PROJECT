"""
app/services/script_capture.py

Process one captured script: OCR the number and mark, match the number
against the session roster, and either auto-write a clean result or send
it back for review. Stores no images and no capture rows -- the phone
holds those.

Verdict per script:
  written -> exact roster match AND confident mark AND session auto_updated
  review  -> everything else (fuzzy, not-in-csv, weak mark, auto off)
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, UploadFile, status
from rapidfuzz import fuzz, process
from sqlalchemy.orm import Session

from ..config.settings import settings
from ..repositories.handwriting_sample import HandwritingSampleRepository
from ..repositories.marking_session import MarkingSessionRepository
from ..schemas.script_capture import (
    MarkProposal,
    ProcessResult,
    StudentSuggestion,
)
from ..utils.image_io import ImageDecodeError, prepare_upload, to_pil
from ..utils.ocr import read_computer_number, read_mark

logger = logging.getLogger(__name__)

# Below this RapidFuzz score a fuzzy match is too weak to suggest.
FUZZY_FLOOR = 80
HANDWRITING_TOP_N = 5
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


class ScriptProcessingService:

    def __init__(self, db: Session) -> None:
        self.sessions = MarkingSessionRepository(db)
        self.samples = HandwritingSampleRepository(db)

    async def process(
        self,
        session_id: int,
        client_id: str,
        number_file: UploadFile,
        mark_file: UploadFile,
        handwriting_file: UploadFile,
        user_id: int,
    ) -> ProcessResult:
        session = self._get_session_or_404(session_id)
        max_mark = float(session.max_mark)

        number_bytes = await self._read(number_file)
        mark_bytes = await self._read(mark_file)
        hw_bytes = await self._read(handwriting_file)

        # Normalise in memory. Nothing is written to disk.
        number_norm = self._prepare(number_bytes)
        mark_norm = self._prepare(mark_bytes)
        hw_norm = self._prepare(hw_bytes)

        number_read = read_computer_number(number_norm)
        mark_read = read_mark(mark_norm, max_mark=max_mark)

        roster = self.sessions.list_student_nos(session_id)

        suggestions, resolved, reason = self._match_number(
            number_read.text, roster, hw_norm
        )

        mark_proposal = MarkProposal(
            value=float(mark_read.text) if mark_read.text is not None else None,
            confidence=mark_read.confidence,
            candidates=[float(c) for c in mark_read.candidates],
        )

        # --- auto-write, only when everything is clean and enabled ---
        auto_write = (
            session.auto_confirm_exact
            and resolved is not None                       # exact roster hit
            and mark_proposal.value is not None
            and mark_read.confidence >= settings.OCR_MARK_AUTOCONFIRM_CONF
        )

        if auto_write:
            self._write_mark(session_id, resolved, mark_proposal.value, user_id)
            return ProcessResult(
                client_id=client_id,
                verdict="written",
                student_no=resolved,
                mark=mark_proposal.value,
            )

        # --- otherwise, back to the phone for review ---
        if reason is None:
            # Exact match, but the mark or the auto flag stopped an
            # auto-write. Still a review, just with a strong suggestion.
            reason = "auto_off" if not session.auto_confirm_exact else "low_mark"

        return ProcessResult(
            client_id=client_id,
            verdict="review",
            reason=reason,
            suggestions=suggestions,
            mark_proposal=mark_proposal,
        )

    # -----------------------------------------------------------------

    def _match_number(self, ocr_number, roster, handwriting_bytes):
        """Returns (suggestions, resolved_student_no, reason).

        resolved_student_no is set ONLY on an exact hit. reason is None
        on an exact hit and names the review cause otherwise."""
        if ocr_number is None:
            return self._handwriting(handwriting_bytes, roster), None, "not_in_csv"

        if ocr_number in roster:
            return (
                [StudentSuggestion(student_no=ocr_number, source="ocr_exact", score=1.0)],
                ocr_number,
                None,
            )

        fuzzy = process.extract(ocr_number, roster, scorer=fuzz.ratio, limit=3)
        strong = [(no, s) for no, s, _ in fuzzy if s >= FUZZY_FLOOR]
        if strong:
            return (
                [StudentSuggestion(student_no=no, source="ocr_fuzzy", score=s / 100.0)
                 for no, s in strong],
                None,
                "fuzzy",
            )

        return self._handwriting(handwriting_bytes, roster), None, "not_in_csv"

    def _handwriting(self, handwriting_bytes, roster):
        try:
            from ml.model import get_embedding_from_image
            embedding = get_embedding_from_image(to_pil(handwriting_bytes))
        except RuntimeError:
            logger.warning("handwriting fallback unavailable: no model")
            return []

        rows = self.samples.search_similar(
            embedding=embedding,
            limit=HANDWRITING_TOP_N,
            model_version=settings.MODEL_VERSION,
            candidate_student_nos=roster or None,
        )
        return [
            StudentSuggestion(
                student_no=r.student_no,
                source="handwriting",
                score=round(1.0 - float(r.distance), 4),
            )
            for r in rows
        ]

    def _write_mark(self, session_id, student_no, mark, user_id):
        row = self.sessions.get_row(session_id, student_no)
        if row is None:
            return
        # Idempotent: if this row already carries an auto ocr_exact mark,
        # a retried submission must not rewrite it.
        if row.mark is not None and row.match_method == "ocr_exact":
            return
        self.sessions.set_mark(
            row, mark=mark, match_method="ocr_exact", marked_by=user_id
        )

    # -----------------------------------------------------------------

    async def _read(self, file: UploadFile) -> bytes:
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported type '{file.content_type}'.",
            )
        return await file.read()

    def _prepare(self, image_bytes: bytes) -> bytes:
        try:
            normalised, _ = prepare_upload(image_bytes)
            return normalised
        except ImageDecodeError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "UNREADABLE", "message": str(exc)},
            )

    def _get_session_or_404(self, session_id: int):
        session = self.sessions.get_session(session_id)
        if session is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"Marking session {session_id} not found.",
            )
        return session