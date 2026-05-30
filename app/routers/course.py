from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..dependencies.database import get_db
from ..schemas.course import CourseCreate, CourseResponse, CourseUpdate
from ..services.course import CourseService

router = APIRouter(prefix="/api/v1/courses", tags=["Courses"])


def get_course_service(db: Session = Depends(get_db)) -> CourseService:
    return CourseService(db)


@router.get("", response_model=list[CourseResponse])
def get_courses(service: CourseService = Depends(get_course_service)):
    return service.get_all()


@router.get("/{course_id}", response_model=CourseResponse)
def get_course(course_id: int, service: CourseService = Depends(get_course_service)):
    return service.get_by_id(course_id)


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
def create_course(payload: CourseCreate, service: CourseService = Depends(get_course_service)):
    return service.create(payload)


@router.patch("/{course_id}", response_model=CourseResponse)
def update_course(
    course_id: int,
    payload: CourseUpdate,
    service: CourseService = Depends(get_course_service),
):
    return service.update(course_id, payload)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: int, service: CourseService = Depends(get_course_service)):
    service.delete(course_id)