import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.enums import ActivityAction
from app.models.user import User
from app.schemas.history import ActivityListResponse, ActivityResponse
from app.services.history_service import HistoryService

router = APIRouter(prefix="/history", tags=["History"])


@router.get(
    "",
    response_model=ActivityListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Activity History",
    description="Retrieve paginated audit log stream for current user with optional filters.",
)
async def list_history(
    entity_type: str | None = Query(
        default=None, description="Filter by entity type, e.g. TASK, PROJECT"
    ),
    entity_id: uuid.UUID | None = Query(default=None, description="Filter by entity UUID"),
    action: ActivityAction | None = Query(default=None, description="Filter by activity action"),
    start_at: datetime | None = Query(
        default=None, description="Filter activities created after timestamp"
    ),
    end_at: datetime | None = Query(
        default=None, description="Filter activities created before timestamp"
    ),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActivityListResponse:
    history_service = HistoryService(db)
    return await history_service.list_history(
        user_id=current_user.id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        start_at=start_at,
        end_at=end_at,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{activity_id}",
    response_model=ActivityResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Activity Log",
    description="Retrieve specific activity log detail scoped to current user.",
)
async def get_activity(
    activity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActivityResponse:
    history_service = HistoryService(db)
    return await history_service.get_history_item(
        user_id=current_user.id,
        activity_id=activity_id,
    )
