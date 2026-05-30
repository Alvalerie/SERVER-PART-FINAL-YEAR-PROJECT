from __future__ import annotations
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..dependencies.database import Base

class Student(Base):
    __tablename__ = "STUDENTS"
    __table_args__ = {"schema": "public"}

    student_no: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    images: Mapped[list["Image"]] = relationship("Image", back_populates="student")
    course_enrollments: Mapped[list["StudentCourse"]] = relationship("StudentCourse", back_populates="student")