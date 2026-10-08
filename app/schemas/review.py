import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class DailyReviewCreate(BaseModel):
    """Payload for creating or upserting a daily review."""

    review_date: date | None = None
    notes: str | None = Field(default=None, max_length=10000)


class DailyReviewUpdate(BaseModel):
    """Payload for partially updating a daily review."""

    notes: str | None = Field(default=None, max_length=10000)
    recalculate: bool = False


class DailyReviewResponse(BaseModel):
    """Safe daily review snapshot response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    review_date: date
    completed_tasks: int
    incomplete_tasks: int
    overdue_tasks: int
    postponed_tasks: int
    notes: str | None
    created_at: datetime
    updated_at: datetime


class DailyReviewListResponse(BaseModel):
    """Paginated list of daily reviews."""

    items: list[DailyReviewResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class WeeklyReviewCreate(BaseModel):
    """Payload for creating or upserting a weekly review."""

    week_start: date | None = None
    notes: str | None = Field(default=None, max_length=10000)


class WeeklyReviewUpdate(BaseModel):
    """Payload for partially updating a weekly review."""

    notes: str | None = Field(default=None, max_length=10000)
    recalculate: bool = False


class WeeklyReviewResponse(BaseModel):
    """Safe weekly review snapshot response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    week_start: date
    week_end: date
    completed_tasks: int
    incomplete_tasks: int
    overdue_tasks: int
    postponed_tasks: int
    notes: str | None
    created_at: datetime
    updated_at: datetime


class WeeklyReviewListResponse(BaseModel):
    """Paginated list of weekly reviews."""

    items: list[WeeklyReviewResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
