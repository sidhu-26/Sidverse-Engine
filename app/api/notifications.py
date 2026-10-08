import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.enums import NotificationType
from app.models.user import User
from app.schemas.notification import (
    NotificationListResponse,
    NotificationResponse,
    NotificationUpdate,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get(
    "",
    response_model=NotificationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Notifications",
    description="Retrieve in-app notifications with read-status filtering and unread metrics.",
)
async def list_notifications(
    read: bool | None = Query(default=None, description="Filter by read status (true/false)"),
    notification_type: NotificationType | None = Query(
        default=None, alias="type", description="Filter by notification type"
    ),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationListResponse:
    notification_service = NotificationService(db)
    return await notification_service.list_notifications(
        user_id=current_user.id,
        is_read=read,
        notification_type=notification_type,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{notification_id}",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Notification Detail",
    description="Retrieve detail for a single notification.",
)
async def get_notification(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationResponse:
    notification_service = NotificationService(db)
    return await notification_service.get_notification(
        notification_id=notification_id, user_id=current_user.id
    )


@router.patch(
    "/{notification_id}",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Notification",
    description="Update notification state (e.g. mark as read).",
)
async def update_notification(
    notification_id: uuid.UUID,
    body: NotificationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationResponse:
    notification_service = NotificationService(db)
    if body.read is True:
        return await notification_service.mark_read(
            notification_id=notification_id, user_id=current_user.id
        )
    return await notification_service.get_notification(
        notification_id=notification_id, user_id=current_user.id
    )


@router.post(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark Notification Read",
    description="Mark a single notification as read.",
)
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationResponse:
    notification_service = NotificationService(db)
    return await notification_service.mark_read(
        notification_id=notification_id, user_id=current_user.id
    )


@router.post(
    "/read-all",
    status_code=status.HTTP_200_OK,
    summary="Mark All Notifications Read",
    description="Mark all unread notifications for current user as read.",
)
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    notification_service = NotificationService(db)
    return await notification_service.mark_all_read(user_id=current_user.id)
