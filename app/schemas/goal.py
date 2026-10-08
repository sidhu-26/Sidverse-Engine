import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import GoalStatus

# ============================================================
# Goal Milestones
# ============================================================


class GoalMilestoneCreate(BaseModel):
    """Payload schema for creating a milestone checkpoint."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    position: int = Field(default=0, ge=0)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Milestone title cannot be empty or whitespace only.")
        return trimmed


class GoalMilestoneUpdate(BaseModel):
    """Payload schema for partially updating a milestone."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    position: int | None = Field(default=None, ge=0)
    is_completed: bool | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Milestone title cannot be empty or whitespace only.")
            return trimmed
        return v


class GoalMilestoneResponse(BaseModel):
    """Public milestone representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    goal_id: uuid.UUID
    title: str
    description: str | None
    position: int
    is_completed: bool
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ============================================================
# Goals
# ============================================================


class GoalCreate(BaseModel):
    """Payload schema for creating a Goal."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    status: GoalStatus = GoalStatus.ACTIVE
    target_date: datetime | None = None
    progress: int = Field(default=0, ge=0, le=100)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Goal title cannot be empty or whitespace only.")
        return trimmed

    @field_validator("target_date")
    @classmethod
    def validate_tz(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("target_date must be timezone-aware.")
        return v


class GoalUpdate(BaseModel):
    """Payload schema for updating a Goal."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    status: GoalStatus | None = None
    target_date: datetime | None = None
    progress: int | None = Field(default=None, ge=0, le=100)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Goal title cannot be empty or whitespace only.")
            return trimmed
        return v

    @field_validator("target_date")
    @classmethod
    def validate_tz(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("target_date must be timezone-aware.")
        return v


class GoalResponse(BaseModel):
    """Public goal representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: str | None
    status: GoalStatus
    target_date: datetime | None
    progress: int
    created_at: datetime
    updated_at: datetime
    milestones: list[GoalMilestoneResponse] = []


class GoalListResponse(BaseModel):
    """Paginated goals collection response."""

    items: list[GoalResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
