from __future__ import annotations
from datetime import date
from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..dependencies.database import Base

class StudentCourse(Base):
    __tablename__ = "STUDENT_COURSE"
    __table_args__ = {"schema": "public"}

    student_id: Mapped[str] = mapped_column(String(10), ForeignKey("public.STUDENTS.student_no"), primary_key=True)
    course_code: Mapped[str] = mapped_column(String(15), ForeignKey("public.COURSES.code"), primary_key=True)
    current_year: Mapped[date] = mapped_column(Date, nullable=False)

    student: Mapped["Student"] = relationship("Student", back_populates="course_enrollments")
    course: Mapped["Course"] = relationship("Course", back_populates="enrollments")