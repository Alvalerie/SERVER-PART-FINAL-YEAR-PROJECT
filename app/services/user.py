from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models.user_model import User
from ..repositories.user import UserRepository
from ..schemas.user import UserCreate, UserUpdate,UserChangePassword
from ..utils.helpers import hash_password, verify_password


class UserService:
    """
    Business logic for User operations.
    Delegates data access to UserRepository.
    """

    def __init__(self, db: Session) -> None:
        self.repo = UserRepository(db)

    def get_all(self) -> list[User]:
        return self.repo.get_all()

    def get_by_id(self, user_id: int) -> User:
        user = self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found",
            )
        return user

    def create(self, payload: UserCreate) -> User:
        if self.repo.get_by_email(payload.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            )
        hashed = hash_password(payload.password)
        return self.repo.create(payload, hashed)

    def update(self, user_id: int, payload: UserUpdate) -> User:
        user = self.get_by_id(user_id)

        # Guard against stealing another user's email
        if payload.email:
            existing = self.repo.get_by_email(payload.email)
            if existing and existing.id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already in use by another account",
                )

        return self.repo.update(user, payload)


    def change_password(self, user_id: int, payload: UserChangePassword) -> None:
        user = self.get_by_id(user_id)

        if not verify_password(payload.current_password, user.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

        if payload.current_password == payload.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from current password",
            )

        hashed = hash_password(payload.new_password)
        self.repo.update_password(user, hashed)

    def delete(self, user_id: int) -> None:
        user = self.get_by_id(user_id)
        self.repo.delete(user)