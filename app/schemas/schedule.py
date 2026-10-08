import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import ScheduleStatus


class ScheduleCreate(BaseModel):
    """Payload schema for creating a new planned schedule block."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    task_id: uuid.UUID | None = None
    start_at: datetime
    end_at: datetime
    status: ScheduleStatus = ScheduleStatus.SCHEDULED

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Title cannot be empty or whitespace only.")
        return trimmed

    @field_validator("start_at", "end_at")
    @classmethod
    def validate_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("Datetime must be timezone-aware.")
        return v

    @model_validator(mode="after")
    def validate_time_range(self) -> "ScheduleCreate":
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be strictly after start_at.")
        return self


class ScheduleUpdate(BaseModel):
    """Payload schema for partially updating a schedule."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    task_id: uuid.UUID | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    status: ScheduleStatus | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Title cannot be empty or whitespace only.")
            return trimmed
        return v

    @field_validator("start_at", "end_at")
    @classmethod
    def validate_tz_aware(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("Datetime must be timezone-aware.")
        return v


class ScheduleResponse(BaseModel):
    """Safe public schedule representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    task_id: uuid.UUID | None
    title: str
    description: str | None
    start_at: datetime
    end_at: datetime
    status: ScheduleStatus
    created_at: datetime
    updated_at: datetime


class ScheduleListResponse(BaseModel):
    """Paginated schedule collection response."""

    items: list[ScheduleResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
