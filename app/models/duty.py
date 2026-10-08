import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import DutyPriority

if TYPE_CHECKING:
    from app.models.recurrence import RecurrenceRule
    from app.models.reminder import Reminder
    from app.models.user import User


class Duty(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Recurring responsibility domain model."""

    __tablename__ = "duties"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    priority: Mapped[DutyPriority] = mapped_column(
        Enum(DutyPriority, name="duty_priority", native_enum=False),
        default=DutyPriority.MEDIUM,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="duties")
    recurrence_rule: Mapped["RecurrenceRule | None"] = relationship(
        "RecurrenceRule",
        back_populates="duty",
        uselist=False,
        cascade="all, delete-orphan",
    )
    reminders: Mapped[list["Reminder"]] = relationship(
        "Reminder",
        back_populates="duty",
        cascade="all, delete-orphan",
    )

    __table_args__ = (Index("ix_duties_user_active", "user_id", "is_active"),)
