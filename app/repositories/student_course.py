from sqlalchemy.orm import Session

from ..models.student_course_model import StudentCourse
from ..schemas.student_course import StudentCourseCreate, StudentCourseUpdate


class StudentCourseRepository:
    """
    Handles all direct database interactions for StudentCourse.
    No business logic lives here — only queries and mutations.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self) -> list[StudentCourse]:
        return self.db.query(StudentCourse).all()

    def get_by_student(self, student_id: str) -> list[StudentCourse]:
        """All course enrollments for a given student."""
        return self.db.query(StudentCourse).filter(StudentCourse.student_id == student_id).all()

    def get_by_course(self, course_code: str) -> list[StudentCourse]:
        """All student enrollments for a given course."""
        return self.db.query(StudentCourse).filter(StudentCourse.course_code == course_code.upper()).all()

    def get_by_id(self, student_id: str, course_code: str) -> StudentCourse | None:
        """Lookup by composite PK."""
        return (
            self.db.query(StudentCourse)
            .filter(
                StudentCourse.student_id == student_id,
                StudentCourse.course_code == course_code.upper(),
            )
            .first()
        )

    def create(self, payload: StudentCourseCreate) -> StudentCourse:
        enrollment = StudentCourse(
            student_id=payload.student_id,
            course_code=payload.course_code.upper(),
            current_year=payload.current_year,
        )
        self.db.add(enrollment)
        self.db.commit()
        self.db.refresh(enrollment)
        return enrollment

    def update(self, enrollment: StudentCourse, payload: StudentCourseUpdate) -> StudentCourse:
        enrollment.current_year = payload.current_year
        self.db.commit()
        self.db.refresh(enrollment)
        return enrollment

    def delete(self, enrollment: StudentCourse) -> None:
        self.db.delete(enrollment)
        self.db.commit()