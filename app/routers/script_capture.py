"""
app/routers/script_capture.py

HTTP layer for the capture flow. Delegates to ScriptCaptureService.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..dependencies.auth import get_current_user
from ..dependencies.database import get_db
from ..models.user_model import User
from ..schemas.script_capture import CaptureOut, CaptureProposal
from ..services.script_capture import ScriptCaptureService

router = APIRouter(prefix="/api/v1/sessions", tags=["captures"])


@router.post(
    "/{session_id}/captures",
    response_model=CaptureProposal,
    status_code=status.HTTP_201_CREATED,
)
async def capture_script(
    session_id: int,
    number_image: UploadFile = File(..., description="Crop of the computer number"),
    mark_image: UploadFile = File(..., description="Crop of the mark"),
    handwriting_image: UploadFile = File(..., description="Crop of the handwriting"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaptureProposal:
    """
    Upload the three crops for one script and get back a proposal:
    who it appears to belong to, and the mark to confirm.

    A proposal, not a decision. Except when the session has
    auto_confirm_exact on and both number and mark read cleanly, the
    lecturer confirms the result with PATCH /sessions/{id}/rows/{no}.
    """
    service = ScriptCaptureService(db)
    return await service.capture(
        session_id=session_id,
        number_file=number_image,
        mark_file=mark_image,
        handwriting_file=handwriting_image,
        user_id=current_user.id,
    )


@router.get("/{session_id}/captures", response_model=list[CaptureOut])
def list_captures(
    session_id: int,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CaptureOut]:
    """
    All captures for a session.

    status_filter='not_in_csv' is the review queue: the scripts whose
    number failed and that a lecturer needs to resolve by hand.
    """
    return ScriptCaptureService(db).list_captures(session_id, status=status_filter)


@router.get("/captures/{capture_id}", response_model=CaptureOut)
def get_capture(
    capture_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaptureOut:
    return ScriptCaptureService(db).get_capture(capture_id)


@router.get("/captures/{capture_id}/{crop}/file")
def get_capture_crop(
    capture_id: int,
    crop: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """
    Serve one of a capture's three crops (crop = number | mark |
    handwriting) so the lecturer can eyeball it against their proposal --
    which is what makes confirmation a real check.
    """
    from fastapi import HTTPException

    service = ScriptCaptureService(db)
    capture = service.get_capture(capture_id)

    paths = {
        "number": capture.number_path,
        "mark": capture.mark_path,
        "handwriting": capture.handwriting_path,
    }
    if crop not in paths:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="crop must be one of: number, mark, handwriting",
        )

    from ..config.settings import settings
    return FileResponse(settings.IMAGES_DIR / paths[crop], media_type="image/jpeg")