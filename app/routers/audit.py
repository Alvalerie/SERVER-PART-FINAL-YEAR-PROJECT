from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..dependencies.auth import require_admin
from ..dependencies.database import get_db
from ..models.user_model import User
from ..schemas.audit import AuditResponse
from ..services.audit import AuditService

router = APIRouter(prefix="/api/v1/audits", tags=["Audit"])


@router.get("", response_model=list[AuditResponse])
def get_audits(
    user_id: int | None = Query(default=None, description="Only entries for this user"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Audit trail, newest first. Admin only."""
    return AuditService(db).get_all(user_id=user_id, limit=limit, offset=offset)
