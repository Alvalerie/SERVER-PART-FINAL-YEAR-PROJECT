from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..dependencies.database import get_db
from ..schemas.student import StudentCreate, StudentResponse, StudentUpdate
from ..services.audit import record_action
from ..services.student import StudentService
from ..dependencies.auth import get_current_user, require_admin
from ..models.user_model import User

router = APIRouter(prefix="/api/v1/students", tags=["Students"])


def get_student_service(db: Session = Depends(get_db)) -> StudentService:
    return StudentService(db)


@router.get("", response_model=list[StudentResponse])
def get_students(
    service: StudentService = Depends(get_student_service),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    students = service.get_all()
    record_action(db, current_user, "Viewed all students")
    return students


@router.get("/{student_id}", response_model=StudentResponse)
def get_student(
    student_id: int,
    service: StudentService = Depends(get_student_service),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    student = service.get_by_id(student_id)
    record_action(db, current_user, f"Viewed student {student_id}")
    return student


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def create_student(
    payload: StudentCreate,
    service: StudentService = Depends(get_student_service),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    student = service.create(payload)
    record_action(db, current_user, f"Created student {payload.student_no} ({payload.name})")
    return student


@router.patch("/{student_id}", response_model=StudentResponse)
def update_student(
    student_id: int,
    payload: StudentUpdate,
    service: StudentService = Depends(get_student_service),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    student = service.update(student_id, payload)
    changes = ", ".join(f"{k}={v}" for k, v in payload.model_dump(exclude_unset=True).items()) or "nothing"
    record_action(db, current_user, f"Updated student {student_id}; {changes}")
    return student

@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(
    student_id: int,
    service: StudentService = Depends(get_student_service),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service.delete(student_id)
    record_action(db, current_user, f"Deleted student {student_id}")
