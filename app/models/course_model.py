from __future__ import annotations
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..dependencies.database import Base

class Course(Base):
    __tablename__ = "COURSES"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)

    enrollments: Mapped[list["StudentCourse"]] = relationship("StudentCourse", back_populates="course")
















