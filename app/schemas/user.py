from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Role(str, Enum):
    admin = "admin"
    lecturer = "lecturer"



# Request schemas

class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Role

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.replace(" ", "").isalpha():
            raise ValueError("Name must contain only letters")
        return value.strip()

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        checks = [
            (lambda v: any(c.isupper() for c in v), "at least one uppercase letter"),
            (lambda v: any(c.islower() for c in v), "at least one lowercase letter"),
            (lambda v: any(c.isdigit() for c in v), "at least one digit"),
            (
                lambda v: any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v),
                "at least one special character",
            ),
        ]
        for check, msg in checks:
            if not check(value):
                raise ValueError(f"Password must contain {msg}")
        return value


class UserUpdate(BaseModel):
    """All fields optional for PATCH requests."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    role: Role | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is not None and not value.replace(" ", "").isalpha():
            raise ValueError("Name must contain only letters")
        return value.strip() if value else value

class UserChangePassword(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        checks = [
            (lambda v: any(c.isupper() for c in v), "at least one uppercase letter"),
            (lambda v: any(c.islower() for c in v), "at least one lowercase letter"),
            (lambda v: any(c.isdigit() for c in v), "at least one digit"),
            (
                lambda v: any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v),
                "at least one special character",
            ),
        ]
        for check, msg in checks:
            if not check(value):
                raise ValueError(f"Password must contain {msg}")
        return value
    

# Response schemas

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: str