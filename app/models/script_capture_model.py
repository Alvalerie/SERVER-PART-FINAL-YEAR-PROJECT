from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime, Float, ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..dependencies.database import Base


class ScriptCapture(Base):
    """
    One captured script: three cropped images plus what OCR and matching
    made of them.

    Separate from SESSION_ROWS because a capture exists BEFORE it is
    resolved to a student -- and a not_in_csv capture may never resolve
    to a roster row at all. That unresolved case is the whole reason the
    handwriting fallback exists, so it needs somewhere to live.
    """

    __tablename__ = "SCRIPT_CAPTURES"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("public.MARKING_SESSIONS.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Bare filenames. Directory comes from settings, same as samples.
    number_path: Mapped[str] = mapped_column(Text, nullable=False)
    mark_path: Mapped[str] = mapped_column(Text, nullable=False)
    handwriting_path: Mapped[str] = mapped_column(Text, nullable=False)

    ocr_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ocr_number_conf: Mapped[float | None] = mapped_column(Float, nullable=True)
    ocr_mark: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ocr_mark_conf: Mapped[float | None] = mapped_column(Float, nullable=True)

    # No FK: the handwriting fallback can suggest the wrong student, and
    # a typed number may not be enrolled. The confirmed truth lives on
    # the session row; this only records what the capture resolved to.
    resolved_student_no: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )
    match_method: Mapped[str | None] = mapped_column(String(20), nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )

    captured_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("public.USER.id"), nullable=False
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    session: Mapped["MarkingSession"] = relationship("MarkingSession")