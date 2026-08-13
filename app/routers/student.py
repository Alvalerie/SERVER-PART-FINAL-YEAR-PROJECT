from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..dependencies.database import get_db
from ..schemas.student import StudentCreate, StudentResponse, StudentUpdate
from ..services.student import StudentService
from ..dependencies.auth import get_current_user, require_admin
from ..models.user_model import User

router = APIRouter(prefix="/api/v1/students", tags=["Students"])


def get_student_service(db: Session = Depends(get_db)) -> StudentService:
    return StudentService(db)


@router.get("", response_model=list[StudentResponse])
def get_students(service: StudentService = Depends(get_student_service), current_user: User = Depends(get_current_user)):
    return service.get_all()


@router.get("/{student_id}", response_model=StudentResponse)
def get_student(student_id: int, service: StudentService = Depends(get_student_service), current_user: User = Depends(get_current_user)):
    return service.get_by_id(student_id)


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def create_student(payload: StudentCreate, service: StudentService = Depends(get_student_service), current_user: User = Depends(require_admin)):
    return service.create(payload)


@router.patch("/{student_id}", response_model=StudentResponse)
def update_student(
    student_id: int,
    payload: StudentUpdate,
    service: StudentService = Depends(get_student_service),
    current_user: User = Depends(require_admin)
):
    return service.update(student_id, payload)

@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(student_id: int, service: StudentService = Depends(get_student_service), current_user: User = Depends(require_admin)):
    service.delete(student_id)