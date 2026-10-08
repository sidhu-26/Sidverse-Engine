import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ReminderStatus

if TYPE_CHECKING:
    from app.models.duty import Duty
    from app.models.schedule import Schedule
    from app.models.task import Task
    from app.models.user import User


class Reminder(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Notification trigger request domain model."""

    __tablename__ = "reminders"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schedules.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    duty_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("duties.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    remind_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    status: Mapped[ReminderStatus] = mapped_column(
        Enum(ReminderStatus, name="reminder_status", native_enum=False),
        default=ReminderStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="reminders")
    task: Mapped["Task | None"] = relationship("Task", back_populates="reminders")
    schedule: Mapped["Schedule | None"] = relationship("Schedule", back_populates="reminders")
    duty: Mapped["Duty | None"] = relationship("Duty", back_populates="reminders")

    __table_args__ = (
        Index("ix_reminders_user_status_remind_at", "user_id", "status", "remind_at"),
    )
