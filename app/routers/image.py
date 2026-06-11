from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..dependencies.database import get_db
from ..schemas.image import (
    ImageResponse,
    ImageUploadResponse,
    RecognitionFallback,
    RecognitionSuccess,
)
from ..services.image import ImageService

router = APIRouter(prefix="/api/v1/images", tags=["Images"])


def get_image_service(db: Session = Depends(get_db)) -> ImageService:
    return ImageService(db)


# Standard reads

@router.get("", response_model=list[ImageResponse])
def get_all_images(service: ImageService = Depends(get_image_service)):
    """Return metadata for every stored image."""
    return service.get_all()


@router.get("/student/{student_id}", response_model=list[ImageResponse])
def get_images_by_student(
    student_id: str, service: ImageService = Depends(get_image_service)
):
    """Return all images belonging to a specific student."""
    return service.get_by_student(student_id)


@router.get("/{image_id}", response_model=ImageResponse)
def get_image(image_id: int, service: ImageService = Depends(get_image_service)):
    """Return metadata for a single image."""
    return service.get_by_id(image_id)


@router.get("/{image_id}/file")
def get_image_file(image_id: int, service: ImageService = Depends(get_image_service)):
    """Serve the actual image file (used in similarity result URLs)."""
    image = service.get_by_id(image_id)
    return FileResponse(image.path)



# Upload a student image (store + vectorise)

@router.post(
    "/upload/{student_id}",
    response_model=ImageUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_student_image(
    student_id: str,
    file: UploadFile = File(...),
    service: ImageService = Depends(get_image_service),
):
    """
    Upload an image for a student.
    - Saves the image to the images/ folder on disk.
    - Converts the image to a vector using the ML model.
    - Stores the file path and vector in the database.

    Accepts: image/jpeg, image/png, image/webp
    """
    return await service.upload_student_image(student_id, file)


# Recognise a student from an image

@router.post(
    "/recognise",
    response_model=RecognitionSuccess | RecognitionFallback,
)
async def recognise_student(
    request: Request,
    file: UploadFile = File(...),
    service: ImageService = Depends(get_image_service),
):
    """
    Attempt to identify a student from an uploaded image.

    **Step 1 — Direct extraction:**
    The ML model tries to read the student number directly from the image
    (e.g. from an ID card). On success, returns:
    ```json
    { "method": "extraction", "student_id": "2021000001" }
    ```

    **Step 2 — Vector similarity (fallback):**
    If extraction fails, the image is converted to a vector and compared
    against all stored student image vectors. Returns the top 5 closest
    matches with their image URLs and the students they belong to:
    ```json
    {
      "method": "vector_similarity",
      "top_matches": [
        { "rank": 1, "student_id": "2021000001", "image_url": "...", "similarity_score": 0.97 },
        ...
      ]
    }
    ```
    """
    return await service.recognise_student(file, request)


# Delete

@router.delete("/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image(image_id: int, service: ImageService = Depends(get_image_service)):
    """Delete an image record from the database and remove the file from disk."""
    service.delete(image_id)