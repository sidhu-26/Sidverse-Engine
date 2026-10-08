import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.enums import ReminderStatus
from app.models.user import User
from app.schemas.reminder import (
    ReminderCreate,
    ReminderListResponse,
    ReminderResponse,
    ReminderUpdate,
)
from app.services.reminder_service import ReminderService

router = APIRouter(prefix="/reminders", tags=["Reminders"])


@router.post(
    "",
    response_model=ReminderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Reminder",
    description="Schedule a reminder for a task, schedule block, or duty.",
)
async def create_reminder(
    body: ReminderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReminderResponse:
    reminder_service = ReminderService(db)
    return await reminder_service.create_reminder(user_id=current_user.id, data=body)


@router.get(
    "",
    response_model=ReminderListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Reminders",
    description="Retrieve paginated reminders belonging to current user.",
)
async def list_reminders(
    status_filter: ReminderStatus | None = Query(
        default=None, alias="status", description="Filter by status"
    ),
    task_id: uuid.UUID | None = Query(default=None, description="Filter by task ID"),
    schedule_id: uuid.UUID | None = Query(default=None, description="Filter by schedule ID"),
    duty_id: uuid.UUID | None = Query(default=None, description="Filter by duty ID"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReminderListResponse:
    reminder_service = ReminderService(db)
    return await reminder_service.list_reminders(
        user_id=current_user.id,
        status=status_filter,
        task_id=task_id,
        schedule_id=schedule_id,
        duty_id=duty_id,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{reminder_id}",
    response_model=ReminderResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Reminder Detail",
    description="Retrieve specific reminder details.",
)
async def get_reminder(
    reminder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReminderResponse:
    reminder_service = ReminderService(db)
    return await reminder_service.get_reminder(reminder_id=reminder_id, user_id=current_user.id)


@router.patch(
    "/{reminder_id}",
    response_model=ReminderResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Reminder",
    description="Reschedule or update reminder status.",
)
async def update_reminder(
    reminder_id: uuid.UUID,
    body: ReminderUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReminderResponse:
    reminder_service = ReminderService(db)
    return await reminder_service.update_reminder(
        reminder_id=reminder_id,
        user_id=current_user.id,
        data=body,
    )


@router.delete(
    "/{reminder_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Reminder",
    description="Delete a reminder and remove its background schedule job.",
)
async def delete_reminder(
    reminder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    reminder_service = ReminderService(db)
    await reminder_service.delete_reminder(reminder_id=reminder_id, user_id=current_user.id)
    return {"message": "Reminder deleted successfully."}
