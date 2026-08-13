"""
app/repositories/handwriting_sample.py

Direct database access for HandwritingSample. No business logic, no
HTTPException -- queries and mutations only.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.handwriting_sample_model import HandwritingSample


class HandwritingSampleRepository:

    def __init__(self, db: Session) -> None:
        self.db = db

    # -----------------------------------------------------------------
    # Reads
    # -----------------------------------------------------------------

    def get_all(self) -> list[HandwritingSample]:
        return self.db.query(HandwritingSample).all()

    def get_by_id(self, sample_id: int) -> HandwritingSample | None:
        return (
            self.db.query(HandwritingSample)
            .filter(HandwritingSample.id == sample_id)
            .first()
        )

    def get_by_student(self, student_no: str) -> list[HandwritingSample]:
        return (
            self.db.query(HandwritingSample)
            .filter(HandwritingSample.student_no == student_no)
            .order_by(HandwritingSample.created_at)
            .all()
        )

    def count_by_student(self, student_no: str) -> int:
        """Drives the is_enrolled flag -- a student below the minimum is
        in the candidate pool but will rarely rank correctly."""
        return (
            self.db.query(func.count(HandwritingSample.id))
            .filter(HandwritingSample.student_no == student_no)
            .scalar()
        )

    def counts_for_students(self, student_nos: list[str]) -> dict[str, int]:
        """
        Sample counts for many students in one query.

        Used at CSV import to warn the lecturer up front: "45 students,
        33 enrolled" -- the other 12 can never be suggested, and finding
        that out mid-marking is far worse than finding it at upload.
        """
        rows = (
            self.db.query(
                HandwritingSample.student_no,
                func.count(HandwritingSample.id).label("n"),
            )
            .filter(HandwritingSample.student_no.in_(student_nos))
            .group_by(HandwritingSample.student_no)
            .all()
        )
        return {row.student_no: row.n for row in rows}

    def stale_embeddings(self, model_version: str, limit: int = 500):
        """Samples not yet re-embedded for the current checkpoint."""
        return (
            self.db.query(HandwritingSample)
            .filter(
                (HandwritingSample.model_version != model_version)
                | (HandwritingSample.model_version.is_(None))
            )
            .limit(limit)
            .all()
        )

    # -----------------------------------------------------------------
    # Similarity search
    # -----------------------------------------------------------------

    def search_similar(
        self,
        embedding: list[float],
        limit: int,
        model_version: str,
        candidate_student_nos: list[str] | None = None,
    ):
        """
        Rank STUDENTS -- not samples -- by their closest sample.

        The DISTINCT ON is the important part. Without it, a student with
        fourteen enrolled samples can fill all five result slots, and the
        lecturer is shown one name five times instead of five names.
        Postgres requires DISTINCT ON columns to lead the ORDER BY, so
        the per-student best is picked in a subquery and the overall
        ranking happens outside it.

        Filtering on model_version is not optional: after a retrain, old
        and new embeddings coexist in the table and comparing across them
        returns confident nonsense with no error raised.
        """
        distance = HandwritingSample.embedding.cosine_distance(embedding)

        best_per_student = (
            self.db.query(
                HandwritingSample.student_no.label("student_no"),
                HandwritingSample.id.label("sample_id"),
                distance.label("distance"),
            )
            .filter(HandwritingSample.embedding.isnot(None))
            .filter(HandwritingSample.model_version == model_version)
        )

        if candidate_student_nos:
            best_per_student = best_per_student.filter(
                HandwritingSample.student_no.in_(candidate_student_nos)
            )

        best_per_student = (
            best_per_student
            .distinct(HandwritingSample.student_no)          # DISTINCT ON
            .order_by(HandwritingSample.student_no, distance)
            .subquery()
        )

        return (
            self.db.query(best_per_student)
            .order_by(best_per_student.c.distance)
            .limit(limit)
            .all()
        )

    # -----------------------------------------------------------------
    # Writes
    # -----------------------------------------------------------------

    def create(
        self,
        student_no: str,
        path: str,
        embedding: list[float],
        model_version: str,
    ) -> HandwritingSample:
        sample = HandwritingSample(
            student_no=student_no,
            path=path,
            embedding=embedding,      # plain list -- pgvector adapts it
            model_version=model_version,
        )
        self.db.add(sample)
        self.db.commit()
        self.db.refresh(sample)
        return sample

    def update_embedding(
        self, sample: HandwritingSample, embedding: list[float], model_version: str
    ) -> HandwritingSample:
        """Used by the re-embed job after a retrain."""
        sample.embedding = embedding
        sample.model_version = model_version
        self.db.commit()
        self.db.refresh(sample)
        return sample

    def delete(self, sample: HandwritingSample) -> None:
        self.db.delete(sample)
        self.db.commit()