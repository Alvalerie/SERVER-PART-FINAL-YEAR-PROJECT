from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..dependencies.database import get_db
from ..schemas.user import UserCreate, UserResponse, UserUpdate, UserChangePassword
from ..services.user import UserService

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


@router.get("", response_model=list[UserResponse])
def get_users(service: UserService = Depends(get_user_service)):
    return service.get_all()


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, service: UserService = Depends(get_user_service)):
    return service.get_by_id(user_id)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, service: UserService = Depends(get_user_service)):
    return service.create(payload)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdate,
    service: UserService = Depends(get_user_service),
):
    return service.update(user_id, payload)

@router.patch("/{user_id}/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    user_id: int,
    payload: UserChangePassword,
    service: UserService = Depends(get_user_service),
):
    service.change_password(user_id, payload)

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, service: UserService = Depends(get_user_service)):
    service.delete(user_id)