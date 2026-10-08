import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationType
from app.models.notification import Notification


class NotificationRepository:
    """Data access repository for Notification domain entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id_and_user(
        self,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Notification | None:
        """Fetch notification by id scoped to user."""
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, notification: Notification) -> Notification:
        """Persist a new notification."""
        self.session.add(notification)
        await self.session.commit()
        await self.session.refresh(notification)
        return notification

    async def update(self, notification: Notification) -> Notification:
        """Update notification entity."""
        await self.session.commit()
        await self.session.refresh(notification)
        return notification

    async def mark_as_read(
        self,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Notification | None:
        """Mark single notification as read."""
        notification = await self.get_by_id_and_user(notification_id, user_id)
        if notification and notification.read_at is None:
            notification.read_at = datetime.now(UTC)
            await self.session.commit()
            await self.session.refresh(notification)
        return notification

    async def mark_all_as_read(self, user_id: uuid.UUID) -> int:
        """Mark all unread notifications for a user as read."""
        now = datetime.now(UTC)
        stmt = (
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=now)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    async def list_notifications(
        self,
        user_id: uuid.UUID,
        is_read: bool | None = None,
        notification_type: NotificationType | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Notification], int, int]:
        """List notifications with read-status filtering, total count, and unread metrics."""
        query = select(Notification).where(Notification.user_id == user_id)

        if is_read is True:
            query = query.where(Notification.read_at.is_not(None))
        elif is_read is False:
            query = query.where(Notification.read_at.is_(None))

        if notification_type is not None:
            query = query.where(Notification.type == notification_type)

        count_stmt = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # Compute unread count for user regardless of pagination
        unread_stmt = select(func.count()).where(
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        )
        unread_count = (await self.session.execute(unread_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(Notification.created_at.desc()).offset(offset).limit(page_size)

        result = await self.session.execute(query)
        return list(result.scalars().all()), total, unread_count
