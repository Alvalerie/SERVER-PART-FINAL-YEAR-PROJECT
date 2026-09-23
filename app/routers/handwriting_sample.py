"""
app/routers/handwriting_sample.py

HTTP layer only: path params, status codes, Depends(). No queries, no
business rules -- everything is delegated to HandwritingSampleService.
"""

from __future__ import annotations
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from ..dependencies.auth import get_current_user, require_admin
from ..dependencies.database import get_db
from ..models.user_model import User
from ..schemas.handwriting_sample import (
    BulkEnrolResult,
    QualityConfigOut,
    SampleOut,
    EnrolledSampleOut,
    WriterSuggestions,
)
from ..services.handwriting_sample import HandwritingSampleService, quality_config

router = APIRouter(prefix="/api/v1", tags=["handwriting"])


# The documented 422 body. The app switches on `code`; `message` is for
# display only and must never be parsed.
QUALITY_REJECTION = {
    422: {
        "description": "Sample rejected by the quality gate",
        "content": {
            "application/json": {
                "examples": {
                    "blurry": {
                        "value": {
                            "detail": {
                                "code": "TOO_BLURRY",
                                "message": "The writing is out of focus. "
                                           "Hold steady and retake.",
                            }
                        }
                    },
                    "strip": {
                        "value": {
                            "detail": {
                                "code": "BAD_ASPECT_RATIO",
                                "message": "This looks like a narrow strip "
                                           "rather than a block of writing.",
                            }
                        }
                    },
                }
            }
        },
    }
}


# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------

@router.get("/config/sample-quality", response_model=QualityConfigOut)
def get_quality_config(
    current_user: User = Depends(get_current_user),
) -> QualityConfigOut:
    """
    Thresholds the mobile app should enforce before uploading.

    Fetched once at startup and cached. Serving the numbers rather than
    hardcoding them in the app is what stops the two sides drifting
    apart, and lets the blur threshold be retuned without an app release.
    """
    return quality_config()


# ---------------------------------------------------------------------
# Enrolment
# ---------------------------------------------------------------------

@router.post(
    "/students/{student_no}/samples",
    response_model=BulkEnrolResult,
    status_code=status.HTTP_201_CREATED,
    responses=QUALITY_REJECTION,
)
async def enrol_samples(
    student_no: str,
    files: Annotated[list[UploadFile], File(description="Handwriting sample images")],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> BulkEnrolResult:
    """
    Batch upload for the mobile app: many samples in one request.

    Partial success is normal, not an error. Each file is reported
    separately in `accepted` / `rejected`; a 422 is only for a request
    that is unusable as a whole.

    Note: Swagger UI cannot render a picker for an array of files. Test
    this route with curl or the app; use the single-file route below to
    test through Swagger.
    """
    service = HandwritingSampleService(db)
    return await service.add_samples(student_no, files)


@router.post(
    "/students/{student_no}/samples/one",
    response_model=EnrolledSampleOut,
    status_code=status.HTTP_201_CREATED,
    responses=QUALITY_REJECTION,
)
async def enrol_one_sample(
    student_no: str,
    file: Annotated[UploadFile, File(description="One handwriting sample image")],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> EnrolledSampleOut:
    """
    Upload a single handwriting sample. Swagger-testable, and useful for
    retrying one image without re-sending a whole batch.

    Raises 422 with `{code, message}` if this image fails the quality
    gate -- unlike the batch route, where a rejection is a list entry.
    """
    service = HandwritingSampleService(db)
    return await service.add_sample(student_no, file)

@router.get("/students/{student_no}/samples", response_model=list[SampleOut])
def list_student_samples(
    student_no: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SampleOut]:
    return HandwritingSampleService(db).get_by_student(student_no)


# ---------------------------------------------------------------------
# Identification
# ---------------------------------------------------------------------

import json


@router.post("/handwriting/identify", response_model=WriterSuggestions)
async def identify_writer(
    file: UploadFile = File(..., description="The handwriting crop to identify"),
    candidates: str = Form(
        ...,
        description='JSON array of unmarked computer numbers to search '
                    'within, e.g. ["2022024567","2021015533"]. This is the '
                    'candidate pool; the server does not hold the CSV.',
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WriterSuggestions:
    """
    Rank likely writers for a handwriting crop, within a candidate pool.

    Returns SUGGESTIONS ONLY. The lecturer confirms; nothing here assigns
    a script to a student.

    `candidates` is the phone's list of still-unmarked computer numbers —
    the only students a not-in-CSV script could plausibly belong to.
    """
    try:
        candidate_list = json.loads(candidates)
    except json.JSONDecodeError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "BAD_CANDIDATES",
                    "message": "candidates must be a JSON array of numbers."},
        )

    if not isinstance(candidate_list, list) or not candidate_list:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "BAD_CANDIDATES",
                    "message": "candidates must be a non-empty JSON array."},
        )

    # Numbers may arrive as ints from JSON; the DB column is a string.
    candidate_list = [str(c).strip() for c in candidate_list if str(c).strip()]

    service = HandwritingSampleService(db)
    return await service.identify_writer(file, candidate_student_nos=candidate_list)

# ---------------------------------------------------------------------
# Sample reads & delete
# ---------------------------------------------------------------------

@router.get("/handwriting-samples", response_model=list[SampleOut])
def list_all_samples(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SampleOut]:
    return HandwritingSampleService(db).get_all()


@router.get("/handwriting-samples/{sample_id}", response_model=SampleOut)
def get_sample(
    sample_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SampleOut:
    return HandwritingSampleService(db).get_by_id(sample_id)


@router.get("/handwriting-samples/{sample_id}/file")
def get_sample_file(
    sample_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """
    Serve the stored image so the lecturer can eyeball a suggested match
    against the script in front of them -- which is what makes the
    confirm step meaningful rather than a rubber stamp.
    """
    service = HandwritingSampleService(db)
    sample = service.get_by_id(sample_id)
    return FileResponse(service.file_path(sample), media_type="image/jpeg")


@router.delete("/handwriting-samples/{sample_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sample(
    sample_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> None:
    HandwritingSampleService(db).delete(sample_id)