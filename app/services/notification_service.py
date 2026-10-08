import math
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.enums import NotificationType
from app.models.notification import Notification
from app.repositories.notification_repository import NotificationRepository
from app.schemas.notification import NotificationListResponse, NotificationResponse


class NotificationService:
    """Business service governing in-app notifications and delivery state."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.notification_repo = NotificationRepository(db)

    async def create_notification(
        self,
        user_id: uuid.UUID,
        type: NotificationType,
        title: str,
        message: str,
        scheduled_for: datetime | None = None,
        delivered_at: datetime | None = None,
    ) -> NotificationResponse:
        """Create and persist a delivery notification."""
        now = datetime.now(UTC)
        notification = Notification(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            scheduled_for=scheduled_for,
            delivered_at=delivered_at or now,
            read_at=None,
        )
        created = await self.notification_repo.create(notification)
        return self._to_response(created)

    async def get_notification(
        self,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> NotificationResponse:
        """Retrieve notification detail for user."""
        notification = await self.notification_repo.get_by_id_and_user(notification_id, user_id)
        if not notification:
            raise AppException(
                message="Notification not found.",
                code="NOTIFICATION_NOT_FOUND",
                status_code=404,
            )
        return self._to_response(notification)

    async def list_notifications(
        self,
        user_id: uuid.UUID,
        is_read: bool | None = None,
        notification_type: NotificationType | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> NotificationListResponse:
        """List notifications with read status filter and pagination."""
        items, total, unread_count = await self.notification_repo.list_notifications(
            user_id=user_id,
            is_read=is_read,
            notification_type=notification_type,
            page=page,
            page_size=page_size,
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return NotificationListResponse(
            items=[self._to_response(n) for n in items],
            total=total,
            unread_count=unread_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def mark_read(
        self,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> NotificationResponse:
        """Mark single notification as read."""
        notification = await self.notification_repo.get_by_id_and_user(notification_id, user_id)
        if not notification:
            raise AppException(
                message="Notification not found.",
                code="NOTIFICATION_NOT_FOUND",
                status_code=404,
            )
        updated = await self.notification_repo.mark_as_read(notification_id, user_id)
        return self._to_response(updated or notification)

    async def mark_all_read(self, user_id: uuid.UUID) -> dict[str, int]:
        """Mark all unread notifications for user as read."""
        count = await self.notification_repo.mark_all_as_read(user_id)
        return {"updated_count": count}

    def _to_response(self, notification: Notification) -> NotificationResponse:
        """Transform Notification ORM entity into NotificationResponse."""
        return NotificationResponse(
            id=notification.id,
            user_id=notification.user_id,
            type=notification.type,
            title=notification.title,
            message=notification.message,
            scheduled_for=notification.scheduled_for,
            delivered_at=notification.delivered_at,
            read_at=notification.read_at,
            created_at=notification.created_at,
            is_read=notification.read_at is not None,
        )
