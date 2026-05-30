from sqlalchemy.orm import Session


from ..models.student_model import Student
from ..schemas.student import StudentCreate, StudentUpdate


class StudentRepository:
    """
    Handles all direct database interactions for User.
    No business logic lives here — only queries and mutations.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self) -> list[Student]:
        return self.db.query(Student).all()

    def get_by_id(self, student_id: int) -> Student | None:
        return self.db.query(Student).filter(Student.student_no == str(student_id)).first()

    def create(self, payload: StudentCreate) -> Student:

        student = Student(
            name=payload.name,
            student_no=str(payload.student_no),
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)
        return student

    def update(self, student: Student, payload: StudentUpdate) -> Student:
        if payload.name is not None:
            student.name = payload.name
        if payload.student_no is not None:
            student.student_no = str(payload.student_no)
        self.db.commit()
        self.db.refresh(student)
        return student
    

    def delete(self, student: Student) -> None:
        self.db.delete(student)
        self.db.commit()