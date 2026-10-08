import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.enums import ScheduleStatus
from app.models.user import User
from app.schemas.schedule import (
    ScheduleCreate,
    ScheduleListResponse,
    ScheduleResponse,
    ScheduleUpdate,
)
from app.services.schedule_service import ScheduleService

router = APIRouter(prefix="/schedules", tags=["Schedules"])


@router.post(
    "",
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Schedule",
    description="Create a new planned schedule block for the authenticated user.",
)
async def create_schedule(
    body: ScheduleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScheduleResponse:
    schedule_service = ScheduleService(db)
    return await schedule_service.create_schedule(user_id=current_user.id, data=body)


@router.get(
    "",
    response_model=ScheduleListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Schedules",
    description="Retrieve a paginated list of schedules belonging to the authenticated user.",
)
async def list_schedules(
    status_filter: ScheduleStatus | None = Query(
        default=None, alias="status", description="Filter by schedule status"
    ),
    task_id: uuid.UUID | None = Query(default=None, description="Filter by associated task UUID"),
    start_after: datetime | None = Query(
        default=None, description="Filter schedules starting on or after timestamp"
    ),
    start_before: datetime | None = Query(
        default=None, description="Filter schedules starting on or before timestamp"
    ),
    end_after: datetime | None = Query(
        default=None, description="Filter schedules ending on or after timestamp"
    ),
    end_before: datetime | None = Query(
        default=None, description="Filter schedules ending on or before timestamp"
    ),
    search: str | None = Query(default=None, description="Search keyword in title or description"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScheduleListResponse:
    schedule_service = ScheduleService(db)
    return await schedule_service.list_schedules(
        user_id=current_user.id,
        status=status_filter,
        task_id=task_id,
        start_after=start_after,
        start_before=start_before,
        end_after=end_after,
        end_before=end_before,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{schedule_id}",
    response_model=ScheduleResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Schedule Detail",
    description="Retrieve the details of a specific schedule block.",
)
async def get_schedule(
    schedule_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScheduleResponse:
    schedule_service = ScheduleService(db)
    return await schedule_service.get_schedule(schedule_id=schedule_id, user_id=current_user.id)


@router.patch(
    "/{schedule_id}",
    response_model=ScheduleResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Schedule",
    description="Partially update a schedule block and enforce transition and overlap rules.",
)
async def update_schedule(
    schedule_id: uuid.UUID,
    body: ScheduleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScheduleResponse:
    schedule_service = ScheduleService(db)
    return await schedule_service.update_schedule(
        schedule_id=schedule_id,
        user_id=current_user.id,
        data=body,
    )


@router.delete(
    "/{schedule_id}",
    status_code=status.HTTP_200_OK,
    summary="Soft Delete Schedule",
    description="Soft-delete a schedule block and record audit activity.",
)
async def delete_schedule(
    schedule_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    schedule_service = ScheduleService(db)
    await schedule_service.delete_schedule(schedule_id=schedule_id, user_id=current_user.id)
    return {"message": "Schedule deleted successfully."}
