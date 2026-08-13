from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime, ForeignKey, Integer, Numeric, String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..dependencies.database import Base


class MarkingSession(Base):
    """One uploaded CSV being worked through. Transient by design:
    exported, then deletable."""

    __tablename__ = "MARKING_SESSIONS"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    max_mark: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)

    csv_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # JSON list of the original headers, in the lecturer's own order.
    csv_columns: Mapped[str] = mapped_column(Text, nullable=False)

    # Which of those headers held the number and the mark. Cannot be
    # constants -- the names came from the lecturer's file.
    comp_no_column: Mapped[str] = mapped_column(String(255), nullable=False)
    mark_column: Mapped[str] = mapped_column(String(255), nullable=False)

    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("public.USER.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    exported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    rows: Mapped[list["SessionRow"]] = relationship(
        "SessionRow", back_populates="session", cascade="all, delete-orphan"
    )


class SessionRow(Base):
    """One line of the CSV."""

    __tablename__ = "SESSION_ROWS"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("public.MARKING_SESSIONS.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Deliberately no FK to STUDENTS: a CSV may list students who have
    # never given handwriting samples. They still need marks.
    student_no: Mapped[str] = mapped_column(String(10), nullable=False)
    csv_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    row_order: Mapped[int] = mapped_column(Integer, nullable=False)

    mark: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    match_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    script_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    marked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    marked_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("public.USER.id"), nullable=True
    )

    # Every column that is not the number or the mark, kept verbatim so
    # export can rebuild the lecturer's own file.
    extra: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    session: Mapped["MarkingSession"] = relationship(
        "MarkingSession", back_populates="rows"
    )