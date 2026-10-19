import logging

from sqlalchemy.orm import Session

from ..models.audit_model import Audit
from ..models.user_model import User
from ..repositories.audit import AuditRepository

logger = logging.getLogger(__name__)


class AuditService:
    """
    Records what lecturers and admins do, and reads the trail back.

    Routers call `record` only after an action has succeeded, so the
    trail lists things that actually happened, not attempts.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = AuditRepository(db)

    def record(self, user_id: int | None, action: str) -> None:
        """
        Write one audit entry.

        Never raises: the action being audited has already been committed,
        so a failure to write the log must not turn a success into a 500
        for the caller. The failure is logged instead.

        Written in its own short session: committing the request's session
        would expire every object it holds, forcing a reload of each one
        while the response is serialised.
        """
        try:
            with Session(bind=self.db.get_bind()) as audit_db:
                AuditRepository(audit_db).create(user_id, action)
        except Exception:
            logger.exception("Failed to write audit entry: user_id=%s action=%r", user_id, action)

    def get_all(self, user_id: int | None = None, limit: int = 100, offset: int = 0) -> list[Audit]:
        return self.repo.get_all(user_id=user_id, limit=limit, offset=offset)


def record_action(db: Session, user: User, action: str) -> None:
    """
    Record `action` as done by `user`.

    The actor's email and role are written into the text as well as
    user_id, so an entry still says who did it after that user account
    is deleted (user_id is then set to NULL).
    """
    try:
        actor = f"{user.email} ({user.role})"
    except Exception:
        # The actor's own row can be gone by now (an admin deleting their
        # own account), so its attributes cannot be reloaded.
        db.rollback()
        actor = "deleted user"
    AuditService(db).record(user.id, f"{actor}: {action}")
