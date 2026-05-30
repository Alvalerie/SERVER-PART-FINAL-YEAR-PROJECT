from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models.student_model import Student
from ..repositories.student import StudentRepository
from ..schemas.student import StudentCreate, StudentUpdate


class StudentService:
    """
    Business logic for Student operations.
    Delegates data access to UserRepository.
    """

    def __init__(self, db: Session) -> None:
        self.repo = StudentRepository(db)

    def get_all(self) -> list[Student]:
        return self.repo.get_all()

    def get_by_id(self, student_id: int) -> Student:
        student = self.repo.get_by_id(student_id)
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student with id {student_id} not found",
            )
        return student

    def create(self, payload: StudentCreate) -> Student:
        if self.repo.get_by_id(payload.student_no):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A student with this student number already exists",
            )

        return self.repo.create(payload)

    def update(self, student_id: int, payload: StudentUpdate) -> Student:
        student = self.get_by_id(student_id)

        # Guard against stealing another students computer number
        if payload.student_no:
            existing = self.repo.get_by_id(payload.student_no)
            if existing and existing.student_no != student_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Student Number already exists in the database",
                )

        return self.repo.update(student, payload)


    def delete(self, student_id: int) -> None:
        student = self.get_by_id(student_id)
        self.repo.delete(student)