import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class DailyReview(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Snapshot review of a single day's accomplishments and tasks."""

    __tablename__ = "daily_reviews"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    review_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    completed_tasks: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    incomplete_tasks: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    overdue_tasks: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    postponed_tasks: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="daily_reviews")

    __table_args__ = (UniqueConstraint("user_id", "review_date", name="uq_daily_review_user_date"),)


class WeeklyReview(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Snapshot review of a week's progress and productivity."""

    __tablename__ = "weekly_reviews"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    week_start: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    week_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    completed_tasks: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    incomplete_tasks: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    overdue_tasks: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    postponed_tasks: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="weekly_reviews")

    __table_args__ = (UniqueConstraint("user_id", "week_start", name="uq_weekly_review_user_week"),)
