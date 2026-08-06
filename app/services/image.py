"""
Image service.

Two main responsibilities:
  1. upload_student_image  – save an image to disk, vectorise it, store path +
                             vector in the DB.
  2. recognise_student     – try direct extraction first; fall back to vector
                             similarity if extraction fails.

The ML model (extraction + vectorisation) is intentionally stubbed out with
clear TODO markers so the real model can be dropped in later without touching
any other part of the codebase.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status, Request
from sqlalchemy.orm import Session

from ..config.settings import settings
from ..models.image_model import Image
from ..repositories.image import ImageRepository
from ..schemas.image import (
    ImageUploadResponse,
    RecognitionFallback,
    RecognitionSuccess,
    SimilarImage,
)

# Number of similar images returned when extraction fails
TOP_N = 5


# ML model stubs
# Replace these two functions with your actual model calls.

def _vectorise(image_bytes: bytes) -> list[float]:
    """
    TODO: Replace with your real vectorisation model.
    Receives raw image bytes; returns a list of floats (the embedding vector).
    """
    raise NotImplementedError("Vectorisation model not yet integrated")


def _extract_student_id(image_bytes: bytes) -> str | None:
    """
    TODO: Replace with your real extraction model.
    Receives raw image bytes; returns the student number string if found,
    or None if extraction fails.
    """
    raise NotImplementedError("Extraction model not yet integrated")


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Pure-Python cosine similarity — replace with numpy/torch when available."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x ** 2 for x in a) ** 0.5
    mag_b = sum(x ** 2 for x in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _parse_vector(vector_str: str) -> list[float]:
    """Convert pgvector string [0.1,0.2,...] back to a list of floats."""
    return [float(v) for v in vector_str.strip("[]").split(",")]


def _vector_to_str(vector: list[float]) -> str:
    """Serialise a vector to pgvector format: [0.1,0.2,0.3]"""
    return "[" + ",".join(str(v) for v in vector) + "]"


# Allowed file types

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _validate_image(file: UploadFile) -> None:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{file.content_type}'. Allowed: jpeg, png, webp",
        )


def _save_to_disk(image_bytes: bytes, filename: str) -> Path:
    """Write image bytes to the images folder and return the full path."""
    dest = settings.IMAGES_DIR / filename
    dest.write_bytes(image_bytes)
    return dest



# Service class

class ImageService:

    def __init__(self, db: Session) -> None:
        self.repo = ImageRepository(db)


    # 1. Upload & store a student image

    async def upload_student_image(
        self, student_id: str, file: UploadFile
    ) -> ImageUploadResponse:
        """
        - Validates the file type.
        - Saves the image to app/images/<student_id>_<uuid>.<ext>.
        - Vectorises the image (stub — replace with real model).
        - Stores the path and vector in the database.
        """
        _validate_image(file)

        image_bytes = await file.read()

        # Build a unique filename
        ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
        filename = f"{student_id}_{uuid.uuid4().hex}.{ext}"

        # Save to disk
        saved_path = _save_to_disk(image_bytes, filename)

        # Vectorise  ← swap _vectorise() stub with real model
        try:
            vector = _vectorise(image_bytes)
            vector_str = _vector_to_str(vector)
        except NotImplementedError:
            # Placeholder — valid pgvector format with correct dimension (10000)
            vector_str = "[" + ",".join(["0.0"] * 10000) + "]"

        # Persist to DB
        image = self.repo.create(
            student_id=student_id,
            path=str(saved_path),
            vector=vector_str,
        )

        return ImageUploadResponse(
            id=image.id,
            student_id=image.student_id,
            path=image.path,
        )

    # 2. Recognise a student from an uploaded image

    async def recognise_student(
        self, file: UploadFile, request: Request
    ) -> RecognitionSuccess | RecognitionFallback:
        """
        Step 1 — Try direct extraction (OCR / ID-card model).
            Success → return RecognitionSuccess with the student_id.
            Failure → proceed to step 2.

        Step 2 — Vectorise the query image and compute cosine similarity
            against every stored vector. Return the top-N matches as
            RecognitionFallback.
        """
        _validate_image(file)
        image_bytes = await file.read()

        # ---- Step 1: direct extraction --------------------------------
        try:
            student_id = _extract_student_id(image_bytes)
            if student_id:
                return RecognitionSuccess(student_id=student_id)
        except NotImplementedError:
            pass  # model not yet integrated — fall through to similarity

        # ---- Step 2: vector similarity --------------------------------
        try:
            query_vector = _vectorise(image_bytes)
        except NotImplementedError:
            # Neither model is integrated yet — return a clear error
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ML models are not yet integrated. Cannot perform recognition.",
            )

        all_images: list[Image] = self.repo.get_all_with_vectors()

        if not all_images:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No images found in the database to compare against",
            )

        # Score every stored image
        scored: list[tuple[float, Image]] = []
        for img in all_images:
            try:
                stored_vector = _parse_vector(img.vector)
                score = _cosine_similarity(query_vector, stored_vector)
                scored.append((score, img))
            except Exception:
                continue  # skip corrupted vectors

        # Sort descending by similarity score
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:TOP_N]

        base_url = str(request.base_url).rstrip("/")

        matches = [
            SimilarImage(
                rank=rank + 1,
                image_id=img.id,
                student_id=img.student_id,
                image_url=f"{base_url}/api/v1/images/{img.id}/file",
                similarity_score=round(score, 4),
            )
            for rank, (score, img) in enumerate(top)
        ]

        return RecognitionFallback(top_matches=matches)

    
    # Standard reads & delete
    
    def get_all(self) -> list[Image]:
        return self.repo.get_all()

    def get_by_id(self, image_id: int) -> Image:
        image = self.repo.get_by_id(image_id)
        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Image with id {image_id} not found",
            )
        return image

    def get_by_student(self, student_id: str) -> list[Image]:
        return self.repo.get_by_student(student_id)

    def delete(self, image_id: int) -> None:
        image = self.get_by_id(image_id)
        # Remove file from disk if it exists
        path = Path(image.path)
        if path.exists():
            path.unlink()
        self.repo.delete(image)