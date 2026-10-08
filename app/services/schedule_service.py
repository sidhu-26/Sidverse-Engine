import math
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.scheduler import app_scheduler
from app.models.enums import ActivityAction, ScheduleStatus
from app.models.schedule import Schedule
from app.repositories.activity_repository import ActivityRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.schedule import (
    ScheduleCreate,
    ScheduleListResponse,
    ScheduleResponse,
    ScheduleUpdate,
)

# Explicit status transitions for schedules
ALLOWED_SCHEDULE_TRANSITIONS: dict[ScheduleStatus, set[ScheduleStatus]] = {
    ScheduleStatus.SCHEDULED: {
        ScheduleStatus.IN_PROGRESS,
        ScheduleStatus.COMPLETED,
        ScheduleStatus.CANCELLED,
    },
    ScheduleStatus.IN_PROGRESS: {
        ScheduleStatus.COMPLETED,
        ScheduleStatus.CANCELLED,
    },
    ScheduleStatus.COMPLETED: {
        ScheduleStatus.SCHEDULED,
    },
    ScheduleStatus.CANCELLED: {
        ScheduleStatus.SCHEDULED,
    },
}


class ScheduleService:
    """Business service governing planned time-blocks and scheduling engine rules."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.schedule_repo = ScheduleRepository(db)
        self.task_repo = TaskRepository(db)
        self.activity_repo = ActivityRepository(db)

    async def create_schedule(
        self,
        user_id: uuid.UUID,
        data: ScheduleCreate,
    ) -> ScheduleResponse:
        """Create a planned schedule block with task validation and overlap checking."""
        # 1. Task Validation (if task_id provided)
        if data.task_id is not None:
            task = await self.task_repo.get_by_id_and_user(data.task_id, user_id)
            if not task:
                raise AppException(
                    message="The specified task does not exist or has been deleted.",
                    code="INVALID_TASK",
                    status_code=400,
                )

        # 2. Overlap Detection
        overlapping = await self.schedule_repo.find_overlapping(
            user_id=user_id,
            start_at=data.start_at,
            end_at=data.end_at,
        )
        if overlapping:
            conflict_titles = [s.title for s in overlapping]
            raise AppException(
                message=(
                    f"Schedule overlaps with existing schedule(s): {', '.join(conflict_titles)}"
                ),
                code="SCHEDULE_OVERLAP",
                status_code=409,
            )

        # 3. Create Entity
        schedule = Schedule(
            user_id=user_id,
            task_id=data.task_id,
            title=data.title,
            description=data.description,
            start_at=data.start_at,
            end_at=data.end_at,
            status=data.status,
        )
        created = await self.schedule_repo.create(schedule)

        # 4. Audit Log
        await self.activity_repo.log_activity(
            user_id=user_id,
            entity_type="SCHEDULE",
            entity_id=created.id,
            action=ActivityAction.SCHEDULE_CREATED,
            metadata={
                "title": created.title,
                "start_at": created.start_at.isoformat(),
                "end_at": created.end_at.isoformat(),
                "status": created.status.value,
                "task_id": str(created.task_id) if created.task_id else None,
            },
        )

        return ScheduleResponse.model_validate(created)

    async def get_schedule(
        self,
        schedule_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ScheduleResponse:
        """Retrieve schedule detail for authenticated user."""
        schedule = await self.schedule_repo.get_by_id_and_user(schedule_id, user_id)
        if not schedule:
            raise AppException(
                message="Schedule not found.",
                code="SCHEDULE_NOT_FOUND",
                status_code=404,
            )
        return ScheduleResponse.model_validate(schedule)

    async def list_schedules(
        self,
        user_id: uuid.UUID,
        status: ScheduleStatus | None = None,
        task_id: uuid.UUID | None = None,
        start_after: datetime | None = None,
        start_before: datetime | None = None,
        end_after: datetime | None = None,
        end_before: datetime | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ScheduleListResponse:
        """List user schedules with pagination and filtering."""
        items, total = await self.schedule_repo.list_schedules(
            user_id=user_id,
            status=status,
            task_id=task_id,
            start_after=start_after,
            start_before=start_before,
            end_after=end_after,
            end_before=end_before,
            search=search,
            page=page,
            page_size=page_size,
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return ScheduleListResponse(
            items=[ScheduleResponse.model_validate(s) for s in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def update_schedule(
        self,
        schedule_id: uuid.UUID,
        user_id: uuid.UUID,
        data: ScheduleUpdate,
    ) -> ScheduleResponse:
        """Partially update schedule with validation, overlap checks, and state transitions."""
        schedule = await self.schedule_repo.get_by_id_and_user(schedule_id, user_id)
        if not schedule:
            raise AppException(
                message="Schedule not found.",
                code="SCHEDULE_NOT_FOUND",
                status_code=404,
            )

        changes: dict[str, dict[str, str | None]] = {}
        old_status = schedule.status
        old_start = schedule.start_at
        old_end = schedule.end_at

        # 1. Task Validation
        if data.task_id is not None and data.task_id != schedule.task_id:
            task = await self.task_repo.get_by_id_and_user(data.task_id, user_id)
            if not task:
                raise AppException(
                    message="The specified task does not exist or has been deleted.",
                    code="INVALID_TASK",
                    status_code=400,
                )
            changes["task_id"] = {
                "old": str(schedule.task_id) if schedule.task_id else None,
                "new": str(data.task_id),
            }
            schedule.task_id = data.task_id

        # 2. General Field Updates
        if data.title is not None and data.title != schedule.title:
            changes["title"] = {"old": schedule.title, "new": data.title}
            schedule.title = data.title

        if data.description is not None and data.description != schedule.description:
            changes["description"] = {"old": schedule.description, "new": data.description}
            schedule.description = data.description

        # 3. Time bounds & Overlap validation
        new_start = data.start_at if data.start_at is not None else schedule.start_at
        new_end = data.end_at if data.end_at is not None else schedule.end_at

        if new_end <= new_start:
            raise AppException(
                message="end_at must be strictly after start_at.",
                code="INVALID_TIME_RANGE",
                status_code=400,
            )

        times_changed = (data.start_at is not None and data.start_at != old_start) or (
            data.end_at is not None and data.end_at != old_end
        )

        if times_changed:
            overlapping = await self.schedule_repo.find_overlapping(
                user_id=user_id,
                start_at=new_start,
                end_at=new_end,
                exclude_id=schedule.id,
            )
            if overlapping:
                conflict_titles = [s.title for s in overlapping]
                raise AppException(
                    message=(
                        f"Schedule overlaps with existing schedule(s): {', '.join(conflict_titles)}"
                    ),
                    code="SCHEDULE_OVERLAP",
                    status_code=409,
                )
            schedule.start_at = new_start
            schedule.end_at = new_end
            await self.activity_repo.log_activity(
                user_id=user_id,
                entity_type="SCHEDULE",
                entity_id=schedule.id,
                action=ActivityAction.SCHEDULE_RESCHEDULED,
                metadata={
                    "old_start_at": old_start.isoformat(),
                    "old_end_at": old_end.isoformat(),
                    "new_start_at": new_start.isoformat(),
                    "new_end_at": new_end.isoformat(),
                },
            )

        # 4. Status Transition
        if data.status is not None and data.status != old_status:
            allowed = ALLOWED_SCHEDULE_TRANSITIONS.get(old_status, set())
            if data.status not in allowed:
                raise AppException(
                    message=(
                        f"Cannot transition schedule status from '{old_status.value}' "
                        f"to '{data.status.value}'."
                    ),
                    code="INVALID_STATUS_TRANSITION",
                    status_code=400,
                )

            schedule.status = data.status

            if data.status == ScheduleStatus.COMPLETED:
                await self.activity_repo.log_activity(
                    user_id=user_id,
                    entity_type="SCHEDULE",
                    entity_id=schedule.id,
                    action=ActivityAction.SCHEDULE_COMPLETED,
                    metadata={"old_status": old_status.value, "new_status": data.status.value},
                )
            elif data.status == ScheduleStatus.CANCELLED:
                await self.activity_repo.log_activity(
                    user_id=user_id,
                    entity_type="SCHEDULE",
                    entity_id=schedule.id,
                    action=ActivityAction.SCHEDULE_CANCELLED,
                    metadata={"old_status": old_status.value, "new_status": data.status.value},
                )
            elif old_status in (ScheduleStatus.COMPLETED, ScheduleStatus.CANCELLED):
                await self.activity_repo.log_activity(
                    user_id=user_id,
                    entity_type="SCHEDULE",
                    entity_id=schedule.id,
                    action=ActivityAction.SCHEDULE_REOPENED,
                    metadata={"old_status": old_status.value, "new_status": data.status.value},
                )
            else:
                changes["status"] = {"old": old_status.value, "new": data.status.value}

        # 5. General Update Activity
        if changes:
            await self.activity_repo.log_activity(
                user_id=user_id,
                entity_type="SCHEDULE",
                entity_id=schedule.id,
                action=ActivityAction.SCHEDULE_UPDATED,
                metadata={"changes": changes},
            )

        updated = await self.schedule_repo.update(schedule)
        return ScheduleResponse.model_validate(updated)

    async def delete_schedule(
        self,
        schedule_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Soft delete schedule and record audit event."""
        schedule = await self.schedule_repo.get_by_id_and_user(schedule_id, user_id)
        if not schedule:
            raise AppException(
                message="Schedule not found.",
                code="SCHEDULE_NOT_FOUND",
                status_code=404,
            )

        await self.schedule_repo.soft_delete(schedule)
        app_scheduler.remove_job(f"schedule:{schedule.id}")

        await self.activity_repo.log_activity(
            user_id=user_id,
            entity_type="SCHEDULE",
            entity_id=schedule.id,
            action=ActivityAction.SCHEDULE_DELETED,
            metadata={"title": schedule.title},
        )
