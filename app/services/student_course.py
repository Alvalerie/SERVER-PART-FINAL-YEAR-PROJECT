from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models.student_course_model import StudentCourse
from ..repositories.student_course import StudentCourseRepository
from ..schemas.student_course import StudentCourseCreate, StudentCourseUpdate


class StudentCourseService:
    """
    Business logic for StudentCourse (enrollment) operations.
    Delegates data access to StudentCourseRepository.
    """

    def __init__(self, db: Session) -> None:
        self.repo = StudentCourseRepository(db)

    def get_all(self) -> list[StudentCourse]:
        return self.repo.get_all()

    def get_by_student(self, student_id: str) -> list[StudentCourse]:
        return self.repo.get_by_student(student_id)

    def get_by_course(self, course_code: str) -> list[StudentCourse]:
        return self.repo.get_by_course(course_code)

    def get_by_id(self, student_id: str, course_code: str) -> StudentCourse:
        enrollment = self.repo.get_by_id(student_id, course_code)
        if not enrollment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Enrollment for student '{student_id}' in course '{course_code}' not found",
            )
        return enrollment

    def create(self, payload: StudentCourseCreate) -> StudentCourse:
        if self.repo.get_by_id(payload.student_id, payload.course_code):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Student '{payload.student_id}' is already enrolled in course '{payload.course_code}'",
            )
        return self.repo.create(payload)

    def update(self, student_id: str, course_code: str, payload: StudentCourseUpdate) -> StudentCourse:
        enrollment = self.get_by_id(student_id, course_code)
        return self.repo.update(enrollment, payload)

    def delete(self, student_id: str, course_code: str) -> None:
        enrollment = self.get_by_id(student_id, course_code)
        self.repo.delete(enrollment)