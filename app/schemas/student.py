from pydantic import BaseModel, ConfigDict, Field, field_validator


# Request schemas

class StudentCreate(BaseModel):
    student_no: int
    name: str = Field(min_length=1, max_length=255)
    

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.replace(" ", "").isalpha():
            raise ValueError("Name must contain only letters")
        return value.strip()

    @field_validator("student_no")
    @classmethod
    def validate_student_no(cls, value: int) -> int:
        value_str = str(value)

        if len(value_str) != 10:
            raise ValueError("Student number must be exactly 10 characters long")

        if not value_str.startswith("20"):
            raise ValueError("Student number must start with '20'")

        if not value_str.isdigit():
            raise ValueError("Student number must contain only positive numbers")

        return value
       


class StudentUpdate(BaseModel):
    """All fields are left optional for PATCH requests."""
    student_no: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is not None and not value.replace(" ", "").isalpha():
            raise ValueError("Name must contain only letters")
        return value.strip() if value else value
    
    @field_validator("student_no")
    @classmethod
    def validate_student_no(cls, value: int) -> int:
        value_str = str(value)

        if len(value_str) != 10:
            raise ValueError("Student number must be exactly 10 characters long")

        if not value_str.startswith("20"):
            raise ValueError("Student number must start with '20'")

        if not value_str.isdigit():
            raise ValueError("Student number must contain only positive numbers")

        return value

    
# Response schemas

class StudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_no: int
    name: str
    