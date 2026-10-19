from __future__ import annotations
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..dependencies.database import Base

class Audit(Base):
    __tablename__ = "AUDIT"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("public.USER.id"), nullable=True)
    action: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Full date and time, not just the day: an audit trail has to say
    # when an action happened, and in what order.
    time_stamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="audit_logs")
