from sqlalchemy.orm import Session

from ..models.course_model import Course
from ..schemas.course import CourseCreate, CourseUpdate


class CourseRepository:
    """
    Handles all direct database interactions for Course.
    No business logic lives here — only queries and mutations.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self) -> list[Course]:
        return self.db.query(Course).all()

    def get_by_id(self, course_id: int) -> Course | None:
        return self.db.query(Course).filter(Course.id == course_id).first()

    def get_by_code(self, code: str) -> Course | None:
        return self.db.query(Course).filter(Course.code == code.upper()).first()

    def create(self, payload: CourseCreate) -> Course:
        course = Course(
            name=payload.name,
            code=payload.code.upper(),
        )
        self.db.add(course)
        self.db.commit()
        self.db.refresh(course)
        return course

    def update(self, course: Course, payload: CourseUpdate) -> Course:
        if payload.name is not None:
            course.name = payload.name
        if payload.code is not None:
            course.code = payload.code.upper()
        self.db.commit()
        self.db.refresh(course)
        return course

    def delete(self, course: Course) -> None:
        self.db.delete(course)
        self.db.commit()