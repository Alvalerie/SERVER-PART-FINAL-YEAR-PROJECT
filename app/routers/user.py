from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..dependencies.database import get_db
from ..schemas.user import UserCreate, UserResponse, UserUpdate, UserChangePassword
from ..services.audit import record_action
from ..services.user import UserService
from ..dependencies.auth import require_admin, get_current_user
from ..models.user_model import User

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


@router.get("", response_model=list[UserResponse])
def get_users(
    service: UserService = Depends(get_user_service),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    users = service.get_all()
    record_action(db, current_user, "Viewed all users")
    return users


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = service.get_by_id(user_id)
    record_action(db, current_user, f"Viewed user {user_id} ({user.email})")
    return user


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    service: UserService = Depends(get_user_service),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = service.create(payload)
    record_action(db, current_user, f"Created {user.role} user {user.id} ({user.email})")
    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdate,
    service: UserService = Depends(get_user_service),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    user = service.update(user_id, payload)
    changed = ", ".join(payload.model_dump(exclude_unset=True)) or "nothing"
    record_action(db, current_user, f"Updated user {user_id} ({user.email}); fields: {changed}")
    return user

@router.patch("/{user_id}/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    user_id: int,
    payload: UserChangePassword,
    service: UserService = Depends(get_user_service),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service.change_password(user_id, payload)
    record_action(db, current_user, f"Changed password of user {user_id}")

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service.delete(user_id)
    record_action(db, current_user, f"Deleted user {user_id}")
