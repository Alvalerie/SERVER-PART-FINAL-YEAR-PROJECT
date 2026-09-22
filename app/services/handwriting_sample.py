"""
app/services/handwriting_sample.py

Two responsibilities:

  1. add_sample       -- normalise, quality-check, embed and store one
                         enrolled handwriting sample for a known student.
  2. identify_writer  -- given an anonymous handwriting crop, rank the
                         candidate students by embedding distance.

identify_writer returns SUGGESTIONS ONLY. Nothing here decides who a
script belongs to; a lecturer confirms. That is a scope commitment from
the proposal, not just a design preference.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..config.settings import settings
from ..models.handwriting_sample_model import HandwritingSample
from ..repositories.handwriting_sample import HandwritingSampleRepository
from ..schemas.handwriting_sample import (
    QualityConfigOut,
    SampleOut,
    EnrolledSampleOut,
    WriterCandidate,
    WriterSuggestions,
    BulkEnrolResult,
    RejectedSample,
)
from ..utils.image_io import ImageDecodeError, prepare_upload, to_pil
from ..utils.image_quality import QualityThresholds, check_sample_quality

from ml.model import get_embedding_from_image

logger = logging.getLogger(__name__)

TOP_N = 5

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

def thresholds_from_settings() -> QualityThresholds:
    """
    Single source of truth for the quality numbers.

    Both the gate and GET /config/sample-quality read from here, so the
    mobile app can never end up enforcing limits the server does not.
    """
    return QualityThresholds(
        min_width=settings.MIN_SAMPLE_WIDTH,
        min_height=settings.MIN_SAMPLE_HEIGHT,
        max_aspect_ratio=settings.MAX_SAMPLE_ASPECT_RATIO,
        min_blur_score=settings.MIN_SAMPLE_BLUR_SCORE,
        min_contrast=settings.MIN_SAMPLE_CONTRAST,
        min_ink_ratio=settings.MIN_SAMPLE_INK_RATIO,
        max_ink_ratio=settings.MAX_SAMPLE_INK_RATIO,
    )


def quality_config() -> QualityConfigOut:
    """Served to the mobile app so it can check before uploading."""
    t = thresholds_from_settings()
    return QualityConfigOut(
        min_width=t.min_width,
        min_height=t.min_height,
        max_aspect_ratio=t.max_aspect_ratio,
        min_blur_score=t.min_blur_score,
        min_contrast=t.min_contrast,
        min_ink_ratio=t.min_ink_ratio,
        max_ink_ratio=t.max_ink_ratio,
        enforce_blur_check=settings.ENFORCE_BLUR_CHECK,
        min_samples_per_student=settings.MIN_SAMPLES_PER_STUDENT,
    )


def _validate_content_type(file: UploadFile) -> None:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{file.content_type}'. "
                   "Allowed: jpeg, png, webp",
        )


def _reject(code: str, message: str) -> HTTPException:
    """
    Structured rejection. The app switches on `code`; `message` is for
    display only and must never be parsed.
    """
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"code": code, "message": message},
    )



class HandwritingSampleService:

    def __init__(self, db: Session) -> None:
        self.repo = HandwritingSampleRepository(db)

    # -----------------------------------------------------------------
    # 1. Enrolment
    # -----------------------------------------------------------------
    async def add_sample(self, student_no: str, file: UploadFile) -> SampleOut:
        _validate_content_type(file)
        contents = await file.read()

        try:
            normalised, image = prepare_upload(contents)
        except ImageDecodeError as exc:
            raise _reject("UNREADABLE", str(exc))

        result = check_sample_quality(
            image,
            thresholds_from_settings(),
            tolerance=settings.SERVER_QUALITY_TOLERANCE,
        )

        blur_only = result.code == "TOO_BLURRY" and not settings.ENFORCE_BLUR_CHECK
        if not result.accepted and not blur_only:
            logger.info("sample rejected student=%s code=%s metrics=%s",
                        student_no, result.code, result.metrics)
            raise _reject(result.code, result.message)

        logger.info("sample accepted student=%s metrics=%s",
                    student_no, result.metrics)

        embedding = get_embedding_from_image(to_pil(normalised))

        filename = f"{student_no}_{uuid.uuid4().hex}.jpg"
        (settings.IMAGES_DIR / filename).write_bytes(normalised)

        try:
            sample = self.repo.create(
                student_no=student_no,
                path=filename,
                embedding=embedding,
                model_version=settings.MODEL_VERSION,
            )
        except Exception:
            (settings.IMAGES_DIR / filename).unlink(missing_ok=True)
            raise

        count = self.repo.count_by_student(student_no)
        return EnrolledSampleOut(
            id=sample.id,
            student_no=sample.student_no,
            path=sample.path,
            created_at=sample.created_at,
            sample_count=count,
            is_enrolled=count >= settings.MIN_SAMPLES_PER_STUDENT,
            quality_metrics=result.metrics,
        )

    async def add_samples(self, student_no: str, files: list[UploadFile]) -> BulkEnrolResult:
        accepted, rejected = [], []

        for file in files:
            try:
                accepted.append(await self.add_sample(student_no, file))

            except HTTPException as exc:
                # Expected: quality gate, wrong content type, unreadable.
                detail = exc.detail if isinstance(exc.detail, dict) else {
                    "code": "REJECTED", "message": str(exc.detail)
                }
                rejected.append(RejectedSample(filename=file.filename, **detail))

            except Exception:
                # Unexpected: embedding blew up, disk full, DB rejected the
                # insert. Log the traceback -- the caller gets a generic
                # message, but you need the real cause.
                logger.exception(
                    "sample processing failed student=%s file=%s",
                    student_no, file.filename,
                )
                rejected.append(RejectedSample(
                    filename=file.filename,
                    code="PROCESSING_ERROR",
                    message="This file could not be processed. Please try again.",
                ))

        count = self.repo.count_by_student(student_no)
        return BulkEnrolResult(
            accepted=accepted,
            rejected=rejected,
            sample_count=count,
            is_enrolled=count >= settings.MIN_SAMPLES_PER_STUDENT,
            samples_needed=max(0, settings.MIN_SAMPLES_PER_STUDENT - count),
        )
    
    # -----------------------------------------------------------------
    # 2. Identification
    # -----------------------------------------------------------------

    async def identify_writer(
        self,
        file: UploadFile,
        candidate_student_nos: list[str] | None = None,
    ) -> WriterSuggestions:
        """
        Rank candidates for an anonymous handwriting crop.

        candidate_student_nos should be the student numbers on the
        current marking session's roster. Narrowing from every enrolled
        student to the ~40 in one class is the single largest accuracy
        gain available, and it costs nothing at the model level.

        Passing None searches everyone -- useful for testing, a bad idea
        in production.
        """
        _validate_content_type(file)
        contents = await file.read()

        try:
            normalised, image = prepare_upload(contents)
        except ImageDecodeError as exc:
            raise _reject("UNREADABLE", str(exc))

        # The same gate, but advisory: a lecturer photographing a script
        # in an exam hall gets a warning, not a refusal. Enrolment can
        # demand a retake because the student is sitting right there.
        # Identification cannot.
        result = check_sample_quality(
            image,
            thresholds_from_settings(),
            tolerance=settings.SERVER_QUALITY_TOLERANCE,
        )

        try:
            embedding = get_embedding_from_image(to_pil(normalised))
        except RuntimeError as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "MODEL_UNAVAILABLE", "message": str(exc)},
            )

        rows = self.repo.search_similar(
            embedding=embedding,
            limit=TOP_N,
            model_version=settings.MODEL_VERSION,
            candidate_student_nos=candidate_student_nos,
        )

        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No enrolled handwriting samples to compare against.",
            )

        candidates = [
            WriterCandidate(
                rank=rank + 1,
                student_no=row.student_no,
                sample_id=row.sample_id,
                distance=round(float(row.distance), 4),
                # For unit-length embeddings cosine distance is in [0, 2].
                # This is a display aid, NOT a probability -- do not let
                # the UI present it as a confidence percentage.
                score=round(1.0 - float(row.distance), 4),
            )
            for rank, row in enumerate(rows)
        ]

        return WriterSuggestions(
            candidates=candidates,
            searched_pool_size=len(candidate_student_nos)
            if candidate_student_nos else None,
            quality_warning=None if result.accepted else result.message,
        )

    # -----------------------------------------------------------------
    # Reads & delete
    # -----------------------------------------------------------------

    def get_all(self) -> list[HandwritingSample]:
        return self.repo.get_all()

    def get_by_id(self, sample_id: int) -> HandwritingSample:
        sample = self.repo.get_by_id(sample_id)
        if not sample:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sample with id {sample_id} not found",
            )
        return sample

    def get_by_student(self, student_no: str) -> list[HandwritingSample]:
        return self.repo.get_by_student(student_no)

    def file_path(self, sample: HandwritingSample) -> Path:
        """path is a bare filename; the directory comes from settings."""
        return settings.IMAGES_DIR / sample.path

    def delete(self, sample_id: int) -> None:
        sample = self.get_by_id(sample_id)
        self.file_path(sample).unlink(missing_ok=True)
        self.repo.delete(sample)