import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import TaskPriority, TaskStatus


class TaskCreate(BaseModel):
    """Payload schema for creating a new task."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    project_id: uuid.UUID | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_at: datetime | None = None
    estimated_minutes: int | None = Field(default=None, gt=0)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Title cannot be empty or whitespace only.")
        return trimmed

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            # Enforce timezone-aware timestamps (defaulting to UTC if naive is passed)
            return v.replace(tzinfo=UTC)
        return v


class TaskUpdate(BaseModel):
    """Payload schema for partially updating an existing task."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    project_id: uuid.UUID | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    due_at: datetime | None = None
    estimated_minutes: int | None = Field(default=None, gt=0)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Title cannot be empty or whitespace only.")
            return trimmed
        return v

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v


class TaskResponse(BaseModel):
    """Safe public task representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    project_id: uuid.UUID | None
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_at: datetime | None
    estimated_minutes: int | None
    completed_at: datetime | None
    is_overdue: bool = False
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    """Paginated task collection response."""

    items: list[TaskResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
