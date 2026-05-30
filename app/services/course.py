from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models.course_model import Course
from ..repositories.course import CourseRepository
from ..schemas.course import CourseCreate, CourseUpdate


class CourseService:
    """
    Business logic for Course operations.
    Delegates data access to CourseRepository.
    """

    def __init__(self, db: Session) -> None:
        self.repo = CourseRepository(db)

    def get_all(self) -> list[Course]:
        return self.repo.get_all()

    def get_by_id(self, course_id: int) -> Course:
        course = self.repo.get_by_id(course_id)
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course with id {course_id} not found",
            )
        return course

    def create(self, payload: CourseCreate) -> Course:
        # Check duplicate code
        if self.repo.get_by_code(payload.code):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A course with code '{payload.code}' already exists",
            )
        return self.repo.create(payload)

    def update(self, course_id: int, payload: CourseUpdate) -> Course:
        course = self.get_by_id(course_id)

        # Guard against duplicate code on another course
        if payload.code:
            existing = self.repo.get_by_code(payload.code)
            if existing and existing.id != course_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Course code '{payload.code}' is already used by another course",
                )

        return self.repo.update(course, payload)

    def delete(self, course_id: int) -> None:
        course = self.get_by_id(course_id)
        self.repo.delete(course)