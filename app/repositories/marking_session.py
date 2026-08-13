"""
app/repositories/marking_session.py

Direct database access for MarkingSession and SessionRow.
No business logic, no HTTPException -- queries and mutations only.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.marking_session_model import MarkingSession, SessionRow
from ..utils.csv_roster import RosterRow


class MarkingSessionRepository:

    def __init__(self, db: Session) -> None:
        self.db = db

    # -----------------------------------------------------------------
    # Sessions
    # -----------------------------------------------------------------

    def create_session(
        self,
        label: str,
        max_mark: float,
        csv_filename: str | None,
        csv_columns: str,
        comp_no_column: str,
        mark_column: str,
        created_by: int,
    ) -> MarkingSession:
        session = MarkingSession(
            label=label,
            max_mark=max_mark,
            csv_filename=csv_filename,
            csv_columns=csv_columns,
            comp_no_column=comp_no_column,
            mark_column=mark_column,
            created_by=created_by,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: int) -> MarkingSession | None:
        return (
            self.db.query(MarkingSession)
            .filter(MarkingSession.id == session_id)
            .first()
        )

    def list_sessions(self, created_by: int | None = None) -> list[MarkingSession]:
        query = self.db.query(MarkingSession)
        if created_by is not None:
            query = query.filter(MarkingSession.created_by == created_by)
        return query.order_by(MarkingSession.created_at.desc()).all()

    def mark_exported(self, session: MarkingSession) -> MarkingSession:
        session.exported_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(session)
        return session

    def delete_session(self, session: MarkingSession) -> None:
        """Rows go with it via ON DELETE CASCADE."""
        self.db.delete(session)
        self.db.commit()

    # -----------------------------------------------------------------
    # Rows
    # -----------------------------------------------------------------

    def bulk_create_rows(self, session_id: int, rows: list[RosterRow]) -> int:
        """
        Insert the parsed roster in one statement.

        bulk_insert_mappings rather than a loop of add(): a 300-student
        class is 300 round trips otherwise, and the whole import is one
        unit of work -- a session with half its roster is worse than no
        session at all.
        """
        if not rows:
            return 0

        self.db.bulk_insert_mappings(
            SessionRow,
            [
                {
                    "session_id": session_id,
                    "student_no": row.student_no,
                    "row_order": row.row_order,
                    "mark": row.mark,
                    "extra": row.extra,
                }
                for row in rows
            ],
        )
        self.db.commit()
        return len(rows)

    def list_rows(self, session_id: int) -> list[SessionRow]:
        """
        Ordered by row_order, never by insertion or primary key.

        Export replays this order, and the lecturer expects their own
        file back in their own order.
        """
        return (
            self.db.query(SessionRow)
            .filter(SessionRow.session_id == session_id)
            .order_by(SessionRow.row_order)
            .all()
        )

    def get_row(self, session_id: int, student_no: str) -> SessionRow | None:
        return (
            self.db.query(SessionRow)
            .filter(
                SessionRow.session_id == session_id,
                SessionRow.student_no == student_no,
            )
            .first()
        )

    def list_student_nos(self, session_id: int) -> list[str]:
        """The candidate pool handed to the handwriting search."""
        rows = (
            self.db.query(SessionRow.student_no)
            .filter(SessionRow.session_id == session_id)
            .all()
        )
        return [row.student_no for row in rows]

    def list_unmarked(self, session_id: int) -> list[SessionRow]:
        """Who is still outstanding -- the lecturer's to-do list."""
        return (
            self.db.query(SessionRow)
            .filter(
                SessionRow.session_id == session_id,
                SessionRow.mark.is_(None),
            )
            .order_by(SessionRow.row_order)
            .all()
        )

    def count_rows(self, session_id: int) -> int:
        return (
            self.db.query(func.count(SessionRow.id))
            .filter(SessionRow.session_id == session_id)
            .scalar()
        )

    def count_marked_rows(self, session_id: int) -> int:
        return (
            self.db.query(func.count(SessionRow.id))
            .filter(
                SessionRow.session_id == session_id,
                SessionRow.mark.isnot(None),
            )
            .scalar()
        )

    def set_mark(
        self,
        row: SessionRow,
        mark: float,
        match_method: str,
        marked_by: int,
        script_path: str | None = None,
    ) -> SessionRow:
        row.mark = mark
        row.match_method = match_method
        row.marked_by = marked_by
        row.marked_at = datetime.now(timezone.utc)
        if script_path is not None:
            row.script_path = script_path

        self.db.commit()
        self.db.refresh(row)
        return row

    def clear_mark(self, row: SessionRow) -> SessionRow:
        """
        Undo. Clears the human fields too, so the CHECK constraint that
        a mark always has a person attached to it still holds.
        """
        row.mark = None
        row.match_method = None
        row.marked_by = None
        row.marked_at = None

        self.db.commit()
        self.db.refresh(row)
        return row