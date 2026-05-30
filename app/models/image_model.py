from __future__ import annotations
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..dependencies.database import Base

class Image(Base):
    __tablename__ = "IMAGES"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    vector: Mapped[str] = mapped_column(Text, nullable=False)
    student_id: Mapped[str] = mapped_column(String(10), ForeignKey("public.STUDENTS.student_no"), nullable=False)

    student: Mapped["Student"] = relationship("Student", back_populates="images")