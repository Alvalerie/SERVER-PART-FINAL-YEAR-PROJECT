"""
app/routers/handwriting_sample.py

HTTP layer only: path params, status codes, Depends(). No queries, no
business rules -- everything is delegated to HandwritingSampleService.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..dependencies.auth import get_current_user, require_admin
from ..dependencies.database import get_db
from ..models.user_model import User
from ..schemas.handwriting_sample import (
    BulkEnrolResult,
    QualityConfigOut,
    SampleOut,
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
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> BulkEnrolResult:
    """
    Upload one or more handwriting samples for a student.

    Partial success is the normal case, not an error: a student submits
    fourteen photos and two are blurry. Failing the whole request would
    force them to re-upload the twelve good ones, so each file is
    reported separately and the accepted ones are kept.

    Individual rejections appear in `rejected`, not as a 422. A 422 is
    returned only if the request itself is unusable.
    """
    service = HandwritingSampleService(db)
    return await service.add_samples(student_no, files)


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

@router.post("/handwriting/identify", response_model=WriterSuggestions)
async def identify_writer(
    file: UploadFile = File(...),
    candidates: str | None = Form(
        None,
        description="Comma-separated student numbers to search within, "
                    "normally the current marking session's roster. "
                    "Omit to search every enrolled student.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WriterSuggestions:
    """
    Rank likely writers for an anonymous handwriting crop.

    Returns SUGGESTIONS ONLY. The lecturer confirms; nothing here
    assigns a script to a student.

    Always pass `candidates` in real use. Narrowing the search from every
    enrolled student to the ~40 on one roster is the largest accuracy
    gain available, and it costs nothing at the model level.
    """
    candidate_list = (
        [c.strip() for c in candidates.split(",") if c.strip()]
        if candidates
        else None
    )

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