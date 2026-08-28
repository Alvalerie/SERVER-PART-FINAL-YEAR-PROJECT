"""
app/routers/script_capture.py

Process one captured script. The server keeps no images.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from ..dependencies.auth import get_current_user
from ..dependencies.database import get_db
from ..models.user_model import User
from ..schemas.script_capture import ProcessResult
from ..services.script_capture import ScriptProcessingService

router = APIRouter(prefix="/api/v1/sessions", tags=["captures"])


@router.post("/{session_id}/process", response_model=ProcessResult)
async def process_script(
    session_id: int,
    client_id: str = Form(..., description="Phone's own id for this capture"),
    number_image: UploadFile = File(...),
    mark_image: UploadFile = File(...),
    handwriting_image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProcessResult:
    """
    Process one script's three crops.

    verdict='written' -> the mark was auto-written; the phone clears it.
    verdict='review'  -> the phone keeps the images and shows the
                         lecturer the suggestions and mark candidates to
                         resolve, then confirms via
                         PATCH /sessions/{id}/rows/{student_no}.

    The images are not stored server-side.
    """
    service = ScriptProcessingService(db)
    return await service.process(
        session_id=session_id,
        client_id=client_id,
        number_file=number_image,
        mark_file=mark_image,
        handwriting_file=handwriting_image,
        user_id=current_user.id,
    )