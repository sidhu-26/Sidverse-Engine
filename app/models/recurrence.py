import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import RecurrenceFrequency

if TYPE_CHECKING:
    from app.models.duty import Duty
    from app.models.user import User


class RecurrenceRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Reusable recurrence rule model for responsibilities and scheduling."""

    __tablename__ = "recurrence_rules"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    duty_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("duties.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
        index=True,
    )
    frequency: Mapped[RecurrenceFrequency] = mapped_column(
        Enum(RecurrenceFrequency, name="recurrence_frequency", native_enum=False),
        nullable=False,
    )
    interval: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    # Comma-separated weekdays e.g. "MON,WED,FRI"
    by_weekday: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    by_month_day: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    start_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    end_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    timezone: Mapped[str] = mapped_column(
        String(50),
        default="Asia/Kolkata",
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User")
    duty: Mapped["Duty | None"] = relationship("Duty", back_populates="recurrence_rule")

    __table_args__ = (UniqueConstraint("duty_id", name="uq_recurrence_rule_duty"),)
