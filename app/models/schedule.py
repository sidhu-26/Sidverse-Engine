import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ScheduleStatus

if TYPE_CHECKING:
    from app.models.reminder import Reminder
    from app.models.task import Task
    from app.models.user import User


class Schedule(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Planned time block domain model."""

    __tablename__ = "schedules"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
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
    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    end_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    status: Mapped[ScheduleStatus] = mapped_column(
        Enum(ScheduleStatus, name="schedule_status", native_enum=False),
        default=ScheduleStatus.SCHEDULED,
        nullable=False,
        index=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="schedules")
    task: Mapped["Task | None"] = relationship("Task", back_populates="schedules")
    reminders: Mapped[list["Reminder"]] = relationship(
        "Reminder",
        back_populates="schedule",
        cascade="all, delete-orphan",
    )

    __table_args__ = (Index("ix_schedules_user_time_range", "user_id", "start_at", "end_at"),)
