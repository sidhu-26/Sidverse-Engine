import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ActivityAction


class ActivityResponse(BaseModel):
    """Safe representation of an activity log entry."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    user_id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID | None
    action: ActivityAction
    metadata: dict[str, Any] | None = Field(default=None, alias="metadata_")
    created_at: datetime


class ActivityListResponse(BaseModel):
    """Paginated activity history response."""

    items: list[ActivityResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
