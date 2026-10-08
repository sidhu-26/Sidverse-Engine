import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.enums import ActivityAction


class ActivityRepository:
    """Repository for Activity audit stream operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log_activity(
        self,
        user_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID | None,
        action: ActivityAction,
        metadata: dict[str, Any] | None = None,
    ) -> Activity:
        """Create and persist an activity log event."""
        activity = Activity(
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            metadata_=metadata,
        )
        self.session.add(activity)
        await self.session.commit()
        await self.session.refresh(activity)
        return activity

    async def get_by_id_and_user(
        self,
        activity_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Activity | None:
        """Fetch a specific activity belonging to user."""
        stmt = select(Activity).where(
            Activity.id == activity_id,
            Activity.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_activities(
        self,
        user_id: uuid.UUID,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        action: ActivityAction | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Activity], int]:
        """List activities for a user with optional filters and pagination."""
        query = select(Activity).where(Activity.user_id == user_id)

        if entity_type is not None:
            query = query.where(Activity.entity_type == entity_type)

        if entity_id is not None:
            query = query.where(Activity.entity_id == entity_id)

        if action is not None:
            query = query.where(Activity.action == action)

        if start_at is not None:
            query = query.where(Activity.created_at >= start_at)

        if end_at is not None:
            query = query.where(Activity.created_at <= end_at)

        count_stmt = select(func.count()).select_from(query.subquery())
        total_count = (await self.session.execute(count_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(Activity.created_at.desc()).offset(offset).limit(page_size)

        result = await self.session.execute(query)
        items = list(result.scalars().all())
        return items, total_count

    async def count_actions_in_range(
        self,
        user_id: uuid.UUID,
        action: ActivityAction,
        start_at: datetime,
        end_at: datetime,
    ) -> int:
        """Count occurrences of a specific action within a time range."""
        stmt = select(func.count(Activity.id)).where(
            Activity.user_id == user_id,
            Activity.action == action,
            Activity.created_at >= start_at,
            Activity.created_at < end_at,
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0
