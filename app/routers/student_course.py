from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..dependencies.database import get_db
from ..schemas.student_course import StudentCourseCreate, StudentCourseResponse, StudentCourseUpdate
from ..services.student_course import StudentCourseService

router = APIRouter(prefix="/api/v1/enrollments", tags=["Enrollments"])


def get_service(db: Session = Depends(get_db)) -> StudentCourseService:
    return StudentCourseService(db)


@router.get("", response_model=list[StudentCourseResponse])
def get_all_enrollments(service: StudentCourseService = Depends(get_service)):
    """Return every enrollment record."""
    return service.get_all()


@router.get("/student/{student_id}", response_model=list[StudentCourseResponse])
def get_enrollments_by_student(student_id: str, service: StudentCourseService = Depends(get_service)):
    """Return all courses a specific student is enrolled in."""
    return service.get_by_student(student_id)


@router.get("/course/{course_code}", response_model=list[StudentCourseResponse])
def get_enrollments_by_course(course_code: str, service: StudentCourseService = Depends(get_service)):
    """Return all students enrolled in a specific course."""
    return service.get_by_course(course_code)


@router.get("/{student_id}/{course_code}", response_model=StudentCourseResponse)
def get_enrollment(
    student_id: str,
    course_code: str,
    service: StudentCourseService = Depends(get_service),
):
    """Return a single enrollment by composite key."""
    return service.get_by_id(student_id, course_code)


@router.post("", response_model=StudentCourseResponse, status_code=status.HTTP_201_CREATED)
def create_enrollment(
    payload: StudentCourseCreate,
    service: StudentCourseService = Depends(get_service),
):
    """Enroll a student in a course."""
    return service.create(payload)


@router.patch("/{student_id}/{course_code}", response_model=StudentCourseResponse)
def update_enrollment(
    student_id: str,
    course_code: str,
    payload: StudentCourseUpdate,
    service: StudentCourseService = Depends(get_service),
):
    """Update the current_year of an enrollment."""
    return service.update(student_id, course_code, payload)


@router.delete("/{student_id}/{course_code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_enrollment(
    student_id: str,
    course_code: str,
    service: StudentCourseService = Depends(get_service),
):
    """Remove a student from a course."""
    service.delete(student_id, course_code)