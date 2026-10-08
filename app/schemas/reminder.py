import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.models.enums import ReminderStatus


class ReminderCreate(BaseModel):
    """Payload schema for creating a new reminder."""

    remind_at: datetime
    task_id: uuid.UUID | None = None
    schedule_id: uuid.UUID | None = None
    duty_id: uuid.UUID | None = None

    @field_validator("remind_at")
    @classmethod
    def validate_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("remind_at must be timezone-aware.")
        return v

    @model_validator(mode="after")
    def validate_single_target(self) -> "ReminderCreate":
        targets = [self.task_id, self.schedule_id, self.duty_id]
        provided = [t for t in targets if t is not None]
        if len(provided) == 0:
            raise ValueError("Reminder must target at least one entity (task, schedule, or duty).")
        if len(provided) > 1:
            raise ValueError("Reminder must target exactly one entity.")
        return self


class ReminderUpdate(BaseModel):
    """Payload schema for partially updating a reminder."""

    remind_at: datetime | None = None
    status: ReminderStatus | None = None

    @field_validator("remind_at")
    @classmethod
    def validate_tz_aware(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("remind_at must be timezone-aware.")
        return v


class ReminderResponse(BaseModel):
    """Safe public reminder representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    task_id: uuid.UUID | None
    schedule_id: uuid.UUID | None
    duty_id: uuid.UUID | None
    remind_at: datetime
    status: ReminderStatus
    created_at: datetime
    updated_at: datetime


class ReminderListResponse(BaseModel):
    """Paginated reminder collection response."""

    items: list[ReminderResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
