import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import NotificationType


class NotificationResponse(BaseModel):
    """Safe public notification representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    type: NotificationType
    title: str
    message: str
    scheduled_for: datetime | None
    delivered_at: datetime | None
    read_at: datetime | None
    created_at: datetime
    is_read: bool = False


class NotificationUpdate(BaseModel):
    """Update payload for notifications."""

    read: bool | None = None


class NotificationListResponse(BaseModel):
    """Paginated notifications response with unread metrics."""

    items: list[NotificationResponse]
    total: int
    unread_count: int = Field(default=0)
    page: int
    page_size: int
    total_pages: int
