"""
app/repositories/script_capture.py

Direct database access for ScriptCapture. No business logic, no
HTTPException.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..models.script_capture_model import ScriptCapture


class ScriptCaptureRepository:

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        session_id: int,
        number_path: str,
        mark_path: str,
        handwriting_path: str,
        captured_by: int,
    ) -> ScriptCapture:
        """Created pending, before OCR runs -- so the three images are
        never lost even if matching later fails."""
        capture = ScriptCapture(
            session_id=session_id,
            number_path=number_path,
            mark_path=mark_path,
            handwriting_path=handwriting_path,
            captured_by=captured_by,
        )
        self.db.add(capture)
        self.db.commit()
        self.db.refresh(capture)
        return capture

    def get_by_id(self, capture_id: int) -> ScriptCapture | None:
        return (
            self.db.query(ScriptCapture)
            .filter(ScriptCapture.id == capture_id)
            .first()
        )

    def list_by_session(
        self, session_id: int, status: str | None = None
    ) -> list[ScriptCapture]:
        query = self.db.query(ScriptCapture).filter(
            ScriptCapture.session_id == session_id
        )
        if status:
            query = query.filter(ScriptCapture.status == status)
        return query.order_by(ScriptCapture.captured_at).all()

    def save_ocr_and_status(
        self,
        capture: ScriptCapture,
        ocr_number: str | None,
        ocr_number_conf: float | None,
        ocr_mark: str | None,
        ocr_mark_conf: float | None,
        status: str,
        resolved_student_no: str | None = None,
        match_method: str | None = None,
    ) -> ScriptCapture:
        """One write for everything OCR and matching produced, so a
        capture never sits half-updated."""
        capture.ocr_number = ocr_number
        capture.ocr_number_conf = ocr_number_conf
        capture.ocr_mark = ocr_mark
        capture.ocr_mark_conf = ocr_mark_conf
        capture.status = status
        capture.resolved_student_no = resolved_student_no
        capture.match_method = match_method
        self.db.commit()
        self.db.refresh(capture)
        return capture

    def mark_confirmed(
        self, capture: ScriptCapture, student_no: str, match_method: str
    ) -> ScriptCapture:
        capture.status = "confirmed"
        capture.resolved_student_no = student_no
        capture.match_method = match_method
        self.db.commit()
        self.db.refresh(capture)
        return capture

    def delete(self, capture: ScriptCapture) -> None:
        self.db.delete(capture)
        self.db.commit()