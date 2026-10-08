import uuid
from typing import Any

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
