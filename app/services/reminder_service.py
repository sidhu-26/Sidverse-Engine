import math
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.exceptions import AppException
from app.core.scheduler import app_scheduler
from app.models.enums import ActivityAction, NotificationType, ReminderStatus
from app.models.reminder import Reminder
from app.repositories.activity_repository import ActivityRepository
from app.repositories.duty_repository import DutyRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.reminder_repository import ReminderRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.reminder import (
    ReminderCreate,
    ReminderListResponse,
    ReminderResponse,
    ReminderUpdate,
)


async def execute_reminder_job(reminder_id: str) -> None:
    """Standalone background job entrypoint executed by APScheduler."""
    async with AsyncSessionLocal() as session:
        service = ReminderService(session)
        await service.trigger_reminder(uuid.UUID(reminder_id))


class ReminderService:
    """Business service governing reminders and triggering notifications."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.reminder_repo = ReminderRepository(db)
        self.task_repo = TaskRepository(db)
        self.schedule_repo = ScheduleRepository(db)
        self.duty_repo = DutyRepository(db)
        self.notification_repo = NotificationRepository(db)
        self.activity_repo = ActivityRepository(db)

    async def create_reminder(
        self,
        user_id: uuid.UUID,
        data: ReminderCreate,
    ) -> ReminderResponse:
        """Create, persist, and schedule a new reminder trigger."""
        now = datetime.now(UTC)
        remind_at = data.remind_at
        if remind_at.tzinfo is None:
            remind_at = remind_at.replace(tzinfo=UTC)

        if remind_at <= now:
            raise AppException(
                message="Reminder time must be strictly in the future.",
                code="INVALID_REMIND_AT",
                status_code=400,
            )

        # 1. Validate Target Entity Ownership & Active State
        target_name = "Item"
        if data.task_id is not None:
            task = await self.task_repo.get_by_id_and_user(data.task_id, user_id)
            if not task:
                raise AppException(
                    message="Target task does not exist or has been deleted.",
                    code="INVALID_TARGET",
                    status_code=400,
                )
            target_name = f"Task: {task.title}"
        elif data.schedule_id is not None:
            schedule = await self.schedule_repo.get_by_id_and_user(data.schedule_id, user_id)
            if not schedule:
                raise AppException(
                    message="Target schedule does not exist or has been deleted.",
                    code="INVALID_TARGET",
                    status_code=400,
                )
            target_name = f"Schedule: {schedule.title}"
        elif data.duty_id is not None:
            duty = await self.duty_repo.get_by_id_and_user(data.duty_id, user_id)
            if not duty:
                raise AppException(
                    message="Target duty does not exist or has been deleted.",
                    code="INVALID_TARGET",
                    status_code=400,
                )
            target_name = f"Duty: {duty.title}"

        # 2. Persist Entity
        reminder = Reminder(
            user_id=user_id,
            task_id=data.task_id,
            schedule_id=data.schedule_id,
            duty_id=data.duty_id,
            remind_at=remind_at,
            status=ReminderStatus.PENDING,
        )
        created = await self.reminder_repo.create(reminder)

        # 3. Register Scheduler Job
        job_id = f"reminder:{created.id}"
        app_scheduler.add_date_job(
            job_id=job_id,
            func=execute_reminder_job,
            run_date=remind_at,
            args=[str(created.id)],
        )

        # 4. Activity Log
        await self.activity_repo.log_activity(
            user_id=user_id,
            entity_type="REMINDER",
            entity_id=created.id,
            action=ActivityAction.REMINDER_CREATED,
            metadata={
                "remind_at": remind_at.isoformat(),
                "target": target_name,
            },
        )

        return ReminderResponse.model_validate(created)

    async def get_reminder(
        self,
        reminder_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ReminderResponse:
        """Retrieve reminder detail for user."""
        reminder = await self.reminder_repo.get_by_id_and_user(reminder_id, user_id)
        if not reminder:
            raise AppException(
                message="Reminder not found.",
                code="REMINDER_NOT_FOUND",
                status_code=404,
            )
        return ReminderResponse.model_validate(reminder)

    async def list_reminders(
        self,
        user_id: uuid.UUID,
        status: ReminderStatus | None = None,
        task_id: uuid.UUID | None = None,
        schedule_id: uuid.UUID | None = None,
        duty_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ReminderListResponse:
        """List reminders for authenticated user."""
        items, total = await self.reminder_repo.list_reminders(
            user_id=user_id,
            status=status,
            task_id=task_id,
            schedule_id=schedule_id,
            duty_id=duty_id,
            page=page,
            page_size=page_size,
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return ReminderListResponse(
            items=[ReminderResponse.model_validate(r) for r in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def update_reminder(
        self,
        reminder_id: uuid.UUID,
        user_id: uuid.UUID,
        data: ReminderUpdate,
    ) -> ReminderResponse:
        """Update reminder timing or cancel reminder."""
        reminder = await self.reminder_repo.get_by_id_and_user(reminder_id, user_id)
        if not reminder:
            raise AppException(
                message="Reminder not found.",
                code="REMINDER_NOT_FOUND",
                status_code=404,
            )

        job_id = f"reminder:{reminder.id}"
        old_status = reminder.status

        if data.remind_at is not None and data.remind_at != reminder.remind_at:
            now = datetime.now(UTC)
            remind_at = data.remind_at
            if remind_at.tzinfo is None:
                remind_at = remind_at.replace(tzinfo=UTC)

            if remind_at <= now:
                raise AppException(
                    message="Reminder time must be strictly in the future.",
                    code="INVALID_REMIND_AT",
                    status_code=400,
                )
            reminder.remind_at = remind_at
            if reminder.status == ReminderStatus.PENDING:
                app_scheduler.add_date_job(
                    job_id=job_id,
                    func=execute_reminder_job,
                    run_date=remind_at,
                    args=[str(reminder.id)],
                )

        if data.status is not None and data.status != old_status:
            reminder.status = data.status
            if data.status == ReminderStatus.CANCELLED:
                app_scheduler.remove_job(job_id)
                await self.activity_repo.log_activity(
                    user_id=user_id,
                    entity_type="REMINDER",
                    entity_id=reminder.id,
                    action=ActivityAction.REMINDER_CANCELLED,
                    metadata={"old_status": old_status.value},
                )

        updated = await self.reminder_repo.update(reminder)
        return ReminderResponse.model_validate(updated)

    async def delete_reminder(
        self,
        reminder_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Delete reminder record and deregister scheduler job."""
        reminder = await self.reminder_repo.get_by_id_and_user(reminder_id, user_id)
        if not reminder:
            raise AppException(
                message="Reminder not found.",
                code="REMINDER_NOT_FOUND",
                status_code=404,
            )

        app_scheduler.remove_job(f"reminder:{reminder.id}")
        await self.reminder_repo.delete(reminder)

    async def trigger_reminder(self, reminder_id: uuid.UUID) -> None:
        """Execute reminder trigger, produce in-app notification, and update state."""
        reminder = await self.reminder_repo.get_by_id(reminder_id)
        if not reminder or reminder.status != ReminderStatus.PENDING:
            return

        user_id = reminder.user_id
        title = "Reminder Alert"
        message = "You have a scheduled reminder."

        if reminder.task_id:
            task = await self.task_repo.get_by_id_and_user(reminder.task_id, user_id)
            if task:
                title = f"Task Reminder: {task.title}"
                message = task.description or f"Task '{task.title}' is scheduled for attention."
        elif reminder.schedule_id:
            schedule = await self.schedule_repo.get_by_id_and_user(reminder.schedule_id, user_id)
            if schedule:
                title = f"Schedule Reminder: {schedule.title}"
                message = schedule.description or f"Upcoming schedule '{schedule.title}'."
        elif reminder.duty_id:
            duty = await self.duty_repo.get_by_id_and_user(reminder.duty_id, user_id)
            if duty:
                title = f"Duty Reminder: {duty.title}"
                message = duty.description or f"Recurring duty '{duty.title}' is due."

        # Atomically create Notification and mark Reminder as TRIGGERED
        from app.models.notification import Notification

        now = datetime.now(UTC)
        notification = Notification(
            user_id=user_id,
            type=NotificationType.REMINDER,
            title=title,
            message=message,
            scheduled_for=reminder.remind_at,
            delivered_at=now,
            read_at=None,
        )
        self.db.add(notification)
        reminder.status = ReminderStatus.TRIGGERED
        await self.db.commit()

        # Log Activity
        await self.activity_repo.log_activity(
            user_id=user_id,
            entity_type="REMINDER",
            entity_id=reminder.id,
            action=ActivityAction.REMINDER_TRIGGERED,
            metadata={"notification_title": title},
        )

        app_scheduler.remove_job(f"reminder:{reminder.id}")

    @classmethod
    async def rebuild_all_pending_reminders(cls) -> int:
        """Load pending reminders from PostgreSQL and register them with APScheduler."""
        now = datetime.now(UTC)
        count = 0
        async with AsyncSessionLocal() as session:
            repo = ReminderRepository(session)
            pending_reminders = await repo.get_all_pending_future_reminders(now)
            for r in pending_reminders:
                job_id = f"reminder:{r.id}"
                app_scheduler.add_date_job(
                    job_id=job_id,
                    func=execute_reminder_job,
                    run_date=r.remind_at,
                    args=[str(r.id)],
                )
                count += 1
        return count
