from pydantic import BaseModel, ConfigDict, Field, field_validator



# Response schemas

class ImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    path: str
    student_id: str


class ImageUploadResponse(BaseModel):
    """Returned after a student image is successfully stored."""
    id: int
    student_id: str
    path: str
    message: str = "Image uploaded and vectorised successfully"


# Recognition result schemas

class RecognitionSuccess(BaseModel):
    """
    Returned when the ML model successfully extracts a student number
    directly from the image (e.g. ID card OCR).
    """
    method: str = "extraction"
    student_id: str
    message: str = "Student identified via direct extraction"


class SimilarImage(BaseModel):
    """One entry in the top-5 vector similarity results."""
    rank: int
    image_id: int
    student_id: str
    image_url: str          # full URL the caller can use to view the image
    similarity_score: float = Field(ge=0.0, le=1.0)


class RecognitionFallback(BaseModel):
    """
    Returned when direct extraction fails and vector similarity is used
    to find the top-5 closest stored images.
    """
    method: str = "vector_similarity"
    message: str = "Direct extraction failed — showing top 5 similar images"
    top_matches: list[SimilarImage]