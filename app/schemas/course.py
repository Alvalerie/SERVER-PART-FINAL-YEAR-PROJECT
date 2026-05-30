from pydantic import BaseModel, ConfigDict, Field, field_validator



# Request schemas
class CourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=15)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.replace(" ", "").isalpha():
            raise ValueError("Course name must contain only letters")
        return value.strip()

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not value.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Course code must contain only letters, numbers, hyphens, or underscores")
        return value


class CourseUpdate(BaseModel):
    """All fields optional for PATCH requests."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, min_length=1, max_length=15)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is not None and not value.replace(" ", "").isalpha():
            raise ValueError("Course name must contain only letters")
        return value.strip() if value else value

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip().upper()
            if not value.replace("-", "").replace("_", "").isalnum():
                raise ValueError("Course code must contain only letters, numbers, hyphens, or underscores")
        return value



# Response schema
class CourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str