from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator



# Request schemas
class StudentCourseCreate(BaseModel):
    student_id: str = Field(min_length=10, max_length=10)
    course_code: str = Field(min_length=1, max_length=15)
    current_year: date

    @field_validator("student_id")
    @classmethod
    def validate_student_id(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("Student ID must contain only digits")
        if not value.startswith("20"):
            raise ValueError("Student ID must start with '20'")
        return value

    @field_validator("course_code")
    @classmethod
    def validate_course_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not value.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Course code must contain only letters, numbers, hyphens, or underscores")
        return value


class StudentCourseUpdate(BaseModel):
    """Only current_year can be updated — the PKs (student_id, course_code) are immutable."""

    current_year: date



# Response schema
class StudentCourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id: str
    course_code: str
    current_year: date