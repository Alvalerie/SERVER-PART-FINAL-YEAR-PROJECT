from sqlalchemy.orm import Session

from app.services import user

from ..models.user_model import User
from ..schemas.user import UserCreate, UserUpdate


class UserRepository:
    """
    Handles all direct database interactions for User.
    No business logic lives here — only queries and mutations.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self) -> list[User]:
        return self.db.query(User).all()

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def create(self, payload: UserCreate, hashed_password: str) -> User:
        user = User(
            name=payload.name,
            email=payload.email,
            password=hashed_password,
            role=payload.role.value,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(self, user: User, payload: UserUpdate) -> User:
        if payload.name is not None:
            user.name = payload.name
        if payload.email is not None:
            user.email = payload.email
        if payload.role is not None:
            user.role = payload.role.value
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def update_password(self, user: User, hashed_password: str) -> None:
        user.password = hashed_password
        self.db.commit()

    def delete(self, user: User) -> None:
        self.db.delete(user)
        self.db.commit()