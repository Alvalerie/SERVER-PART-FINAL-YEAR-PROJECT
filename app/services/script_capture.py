"""
app/services/script_capture.py

The capture flow. A lecturer uploads three crops per script -- computer
number, mark, handwriting -- and this proposes who the script belongs to
and what mark it carries. It PROPOSES; the lecturer confirms elsewhere
(set_mark). The one exception is auto_confirm_exact, which is per-session
and off by default.

Number  -> OCR, matched against the roster: exact / fuzzy / not-in-csv.
Mark    -> OCR, pre-filled as a candidate, never written by this service.
Writing -> handwriting crop, embedded and ranked against the roster only
           when the number fails to match. Always uploaded, used on demand.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException, UploadFile, status
from rapidfuzz import fuzz, process
from sqlalchemy.orm import Session

from ..config.settings import settings
from ..repositories.handwriting_sample import HandwritingSampleRepository
from ..repositories.marking_session import MarkingSessionRepository
from ..repositories.script_capture import ScriptCaptureRepository
from ..schemas.script_capture import (
    CaptureProposal,
    MarkProposal,
    StudentSuggestion,
)
from ..utils.image_io import ImageDecodeError, prepare_upload, to_pil
from ..utils.ocr import read_computer_number, read_mark

logger = logging.getLogger(__name__)

# Below this RapidFuzz score, a fuzzy "match" is too weak to suggest and
# the capture is treated as not-in-csv instead.
FUZZY_FLOOR = 80

# How many students the handwriting fallback ranks and returns.
HANDWRITING_TOP_N = 5

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


class ScriptCaptureService:

    def __init__(self, db: Session) -> None:
        self.captures = ScriptCaptureRepository(db)
        self.sessions = MarkingSessionRepository(db)
        self.samples = HandwritingSampleRepository(db)

    # -----------------------------------------------------------------

    async def capture(
        self,
        session_id: int,
        number_file: UploadFile,
        mark_file: UploadFile,
        handwriting_file: UploadFile,
        user_id: int,
    ) -> CaptureProposal:
        session = self._get_session_or_404(session_id)
        max_mark = float(session.max_mark)

        # Read all three uploads up front. If any is unreadable the whole
        # capture is rejected -- there is no point storing two of three.
        number_bytes = await self._read_upload(number_file)
        mark_bytes = await self._read_upload(mark_file)
        hw_bytes = await self._read_upload(handwriting_file)

        # Normalise + store all three BEFORE OCR. If OCR then throws, the
        # images are safe and the capture is recoverable.
        number_norm, _ = self._prepare(number_bytes)
        mark_norm, _ = self._prepare(mark_bytes)
        hw_norm, _ = self._prepare(hw_bytes)

        number_path = self._store(number_norm, session_id, "num")
        mark_path = self._store(mark_norm, session_id, "mark")
        hw_path = self._store(hw_norm, session_id, "hw")

        capture = self.captures.create(
            session_id=session_id,
            number_path=number_path,
            mark_path=mark_path,
            handwriting_path=hw_path,
            captured_by=user_id,
        )

        # --- read the number and the mark ---
        number_read = read_computer_number(number_norm)
        mark_read = read_mark(mark_norm, max_mark=max_mark)

        roster = self.sessions.list_student_nos(session_id)

        # --- resolve the number against the roster ---
        suggestions, match_status, match_method, resolved = self._resolve_number(
            number_read.text, roster, hw_norm, session_id
        )

        self.captures.save_ocr_and_status(
            capture,
            ocr_number=number_read.text,
            ocr_number_conf=number_read.confidence,
            ocr_mark=mark_read.text,
            ocr_mark_conf=mark_read.confidence,
            status=match_status,
            resolved_student_no=resolved,
            match_method=match_method,
        )

        mark_proposal = MarkProposal(
            value=float(mark_read.text) if mark_read.text is not None else None,
            confidence=mark_read.confidence,
            candidates=[float(c) for c in mark_read.candidates],
        )

        # --- auto-confirm, if and only if it is switched on AND safe ---
        auto_confirmed = False
        if (
            session.auto_confirm_exact
            and match_status == "matched"
            and mark_proposal.value is not None
            and mark_read.confidence >= settings.OCR_MARK_AUTOCONFIRM_CONF
        ):
            self._auto_confirm(
                session_id, resolved, mark_proposal.value, capture, user_id
            )
            auto_confirmed = True

        return CaptureProposal(
            capture_id=capture.id,
            status=match_status,
            ocr_number=number_read.text,
            number_confidence=number_read.confidence,
            suggestions=suggestions,
            mark=mark_proposal,
            auto_confirmed=auto_confirmed,
        )

    # -----------------------------------------------------------------
    # Number resolution
    # -----------------------------------------------------------------

    def _resolve_number(
        self,
        ocr_number: str | None,
        roster: list[str],
        handwriting_bytes: bytes,
        session_id: int,
    ) -> tuple[list[StudentSuggestion], str, str | None, str | None]:
        """
        Returns (suggestions, status, match_method, resolved_student_no).

        resolved_student_no is set only on an exact match -- a fuzzy or
        handwriting result is a suggestion the lecturer must choose, so
        it stays None until they confirm.
        """
        # No number read at all -> straight to handwriting.
        if ocr_number is None:
            return (
                self._handwriting_fallback(handwriting_bytes, roster, session_id),
                "not_in_csv",
                None,
                None,
            )

        # Exact hit on the roster.
        if ocr_number in roster:
            return (
                [StudentSuggestion(
                    student_no=ocr_number, source="ocr_exact", score=1.0
                )],
                "matched",
                "ocr_exact",
                ocr_number,
            )

        # Fuzzy: an OCR slip (a dropped or swapped digit) against the
        # roster. Scored on the ~40 numbers in this class, not the whole
        # student table.
        fuzzy = process.extract(
            ocr_number, roster, scorer=fuzz.ratio, limit=3
        )
        strong = [(no, score) for no, score, _ in fuzzy if score >= FUZZY_FLOOR]

        if strong:
            return (
                [StudentSuggestion(
                    student_no=no, source="ocr_fuzzy", score=score / 100.0
                ) for no, score in strong],
                "fuzzy",
                "ocr_fuzzy",
                None,
            )

        # Number read but nothing on the roster resembles it. Fall back
        # to handwriting -- this is the case the whole module exists for.
        return (
            self._handwriting_fallback(handwriting_bytes, roster, session_id),
            "not_in_csv",
            None,
            None,
        )

    def _handwriting_fallback(
        self, handwriting_bytes: bytes, roster: list[str], session_id: int
    ) -> list[StudentSuggestion]:
        """Embed the handwriting crop and rank roster students by their
        closest enrolled sample. Suggestions only."""
        try:
            from ml.model import get_embedding_from_image
            embedding = get_embedding_from_image(to_pil(handwriting_bytes))
        except RuntimeError:
            # Model checkpoint missing -- handwriting fallback is simply
            # unavailable, but the capture is still recorded. The lecturer
            # types the number manually.
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
                student_no=row.student_no,
                source="handwriting",
                score=round(1.0 - float(row.distance), 4),
            )
            for row in rows
        ]

    # -----------------------------------------------------------------
    # Auto-confirm (off by default, per session)
    # -----------------------------------------------------------------

    def _auto_confirm(
        self, session_id, student_no, mark, capture, user_id
    ) -> None:
        row = self.sessions.get_row(session_id, student_no)
        if row is None:
            return  # matched the roster list but no row -- should not happen
        self.sessions.set_mark(
            row,
            mark=mark,
            match_method="ocr_exact",
            marked_by=user_id,
            script_path=capture.handwriting_path,
        )
        self.captures.mark_confirmed(capture, student_no, "ocr_exact")

    # -----------------------------------------------------------------
    # Reads
    # -----------------------------------------------------------------

    def list_captures(self, session_id: int, status: str | None = None):
        self._get_session_or_404(session_id)
        return self.captures.list_by_session(session_id, status=status)

    def get_capture(self, capture_id: int):
        capture = self.captures.get_by_id(capture_id)
        if capture is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"Capture {capture_id} not found.",
            )
        return capture

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    async def _read_upload(self, file: UploadFile) -> bytes:
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported type '{file.content_type}'.",
            )
        return await file.read()

    def _prepare(self, image_bytes: bytes):
        try:
            return prepare_upload(image_bytes)
        except ImageDecodeError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "UNREADABLE", "message": str(exc)},
            )

    def _store(self, image_bytes: bytes, session_id: int, kind: str) -> str:
        filename = f"capture_{session_id}_{kind}_{uuid.uuid4().hex}.jpg"
        (settings.IMAGES_DIR / filename).write_bytes(image_bytes)
        return filename

    def _get_session_or_404(self, session_id: int):
        session = self.sessions.get_session(session_id)
        if session is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"Marking session {session_id} not found.",
            )
        return session