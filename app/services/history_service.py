import math
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.activity import Activity
from app.models.enums import ActivityAction
from app.repositories.activity_repository import ActivityRepository
from app.schemas.history import ActivityListResponse, ActivityResponse


class HistoryService:
    """Service for querying and retrieving audit activity history."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.activity_repo = ActivityRepository(db)

    async def list_history(
        self,
        user_id: uuid.UUID,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        action: ActivityAction | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ActivityListResponse:
        """List authenticated user's activity history with filtering and pagination."""
        items, total = await self.activity_repo.list_activities(
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            start_at=start_at,
            end_at=end_at,
            page=page,
            page_size=page_size,
        )

        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return ActivityListResponse(
            items=[self._to_response(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_history_item(
        self,
        user_id: uuid.UUID,
        activity_id: uuid.UUID,
    ) -> ActivityResponse:
        """Retrieve single activity log by ID scoped to current user."""
        activity = await self.activity_repo.get_by_id_and_user(activity_id, user_id)
        if not activity:
            raise AppException(
                message="Activity not found.",
                code="ACTIVITY_NOT_FOUND",
                status_code=404,
            )
        return self._to_response(activity)

    def _to_response(self, activity: Activity) -> ActivityResponse:
        """Convert Activity ORM entity to ActivityResponse."""
        return ActivityResponse(
            id=activity.id,
            user_id=activity.user_id,
            entity_type=activity.entity_type,
            entity_id=activity.entity_id,
            action=activity.action,
            metadata_=activity.metadata_,
            created_at=activity.created_at,
        )
