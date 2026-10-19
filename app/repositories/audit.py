from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..models.audit_model import Audit


class AuditRepository:
    """
    Handles all direct database interactions for Audit.
    No business logic lives here — only queries and mutations.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, user_id: int | None, action: str) -> Audit:
        entry = Audit(
            user_id=user_id,
            action=action,
            time_stamp=datetime.now(UTC),
        )
        self.db.add(entry)
        self.db.commit()
        return entry

    def get_all(self, user_id: int | None = None, limit: int = 100, offset: int = 0) -> list[Audit]:
        query = self.db.query(Audit)
        if user_id is not None:
            query = query.filter(Audit.user_id == user_id)
        return (
            query.order_by(Audit.time_stamp.desc(), Audit.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
