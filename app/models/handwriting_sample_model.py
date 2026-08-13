from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..dependencies.database import Base


class HandwritingSample(Base):
    """
    An enrolled handwriting sample belonging to a known student.

    Enrolment is once-ever, so rows here are long-lived: the original
    image on disk must be kept, not just the embedding, because every
    retrain requires re-embedding from source.
    """

    __tablename__ = "HANDWRITING_SAMPLES"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Bare filename, not an absolute path. The directory comes from
    # settings.IMAGES_DIR so the rows survive a move to a container.
    path: Mapped[str] = mapped_column(Text, nullable=False)

    student_no: Mapped[str] = mapped_column(
        String(10),
        ForeignKey("public.STUDENTS.student_no"),
        nullable=False,
        index=True,
    )

    # Nullable so a re-embed job can null-then-fill in batches without
    # dropping rows. A NULL embedding is simply skipped when searching.
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(256), nullable=True
    )

    # Embeddings from different checkpoints are NOT comparable. Every
    # similarity query filters on this.
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    student: Mapped["Student"] = relationship(
        "Student", back_populates="handwriting_samples"
    )