"""
app/routers/marking_session.py

HTTP layer only: path params, status codes, Depends(). No queries, no
business rules -- everything is delegated to MarkingSessionService.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session


from ..dependencies.auth import get_current_user
from ..dependencies.database import get_db
from ..models.user_model import User
from ..schemas.marking_session import (
    SessionImportResult,
    SessionOut,
    SessionProgress,
    SessionRowOut,
    SetMarkRequest,
)
from ..services.marking_session import MarkingSessionService

router = APIRouter(prefix="/api/v1/sessions", tags=["marking sessions"])


CSV_REJECTION = {
    422: {
        "description": "The CSV could not be used",
        "content": {
            "application/json": {
                "example": {
                    "detail": {
                        "code": "CSV_UNUSABLE",
                        "message": "No column of computer numbers found. "
                                   "Expected 10-digit values beginning with 20.",
                    }
                }
            }
        },
    }
}


# ---------------------------------------------------------------------
# Create & list
# ---------------------------------------------------------------------

@router.post(
    "",
    response_model=SessionImportResult,
    status_code=status.HTTP_201_CREATED,
    responses=CSV_REJECTION,
)
async def create_session(
    label: str = Form(..., description="e.g. 'CSC4035 Final 2026'"),
    max_mark: float = Form(..., gt=0, description="Marks available on this paper"),
    file: UploadFile = File(..., description="The lecturer's CSV"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionImportResult:
    """
    Upload a CSV and start a marking session.

    The response is a briefing, not just a receipt: rows skipped, and how
    many of these students the handwriting fallback could actually
    suggest. Finding out mid-session that a third of the class was never
    enrolled is far worse than being told before starting.
    """
    service = MarkingSessionService(db)
    return await service.create_from_csv(
        label=label, max_mark=max_mark, file=file, user_id=current_user.id
    )


@router.get("", response_model=list[SessionOut])
def list_sessions(
    mine_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SessionOut]:
    return MarkingSessionService(db).list_sessions(
        user_id=current_user.id if mine_only else None
    )


# ---------------------------------------------------------------------
# Progress & rows
# ---------------------------------------------------------------------

@router.get("/{session_id}", response_model=SessionProgress)
def get_progress(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionProgress:
    """23 of 45 marked, 22 remaining."""
    return MarkingSessionService(db).get_progress(session_id)


@router.get("/{session_id}/rows", response_model=list[SessionRowOut])
def list_rows(
    session_id: int,
    unmarked_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SessionRowOut]:
    """
    The roster. unmarked_only=true gives the outstanding list -- which
    is how the lecturer finds the scripts that never turned up.
    """
    return MarkingSessionService(db).list_rows(
        session_id, unmarked_only=unmarked_only
    )


@router.patch("/{session_id}/rows/{student_no}", response_model=SessionRowOut)
def set_mark(
    session_id: int,
    student_no: str,
    body: SetMarkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionRowOut:
    """
    Record a confirmed mark.

    This is the only route that writes a mark, and it is always a human
    action. OCR and handwriting identification propose; the lecturer
    decides. match_method records which path led here, which is also
    the data you need to report how often each one worked.
    """
    service = MarkingSessionService(db)
    return service.set_mark(
        session_id=session_id,
        student_no=student_no,
        mark=body.mark,
        match_method=body.match_method,
        user_id=current_user.id,
        script_path=body.script_path,
    )


@router.delete(
    "/{session_id}/rows/{student_no}/mark",
    response_model=SessionRowOut,
)
def clear_mark(
    session_id: int,
    student_no: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionRowOut:
    """Undo a mark. Marking a script to the wrong student is the mistake
    this system makes most easily, so undo has to be one action."""
    return MarkingSessionService(db).clear_mark(session_id, student_no)


# ---------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------

@router.get("/{session_id}/export")
def export_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    Download the lecturer's CSV with marks filled in.

    Same columns, same order, same rows -- unmarked scripts come back
    blank rather than zero.

    utf-8-sig on the way out so Excel opens it correctly, mirroring the
    BOM handling on import.
    """
    csv_text, filename = MarkingSessionService(db).export_csv(session_id)

    return StreamingResponse(
        iter([csv_text.encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------

@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Remove a session and its rows.

    Expected housekeeping, not an unusual event: once exported, the CSV
    is the record and the session has served its purpose.
    """
    MarkingSessionService(db).delete_session(session_id)