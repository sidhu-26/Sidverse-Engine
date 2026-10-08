import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ReminderStatus
from app.models.reminder import Reminder


class ReminderRepository:
    """Data access repository for Reminder domain entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id_and_user(
        self,
        reminder_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Reminder | None:
        """Fetch reminder by id scoped to user."""
        stmt = select(Reminder).where(
            Reminder.id == reminder_id,
            Reminder.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, reminder_id: uuid.UUID) -> Reminder | None:
        """Fetch reminder by id directly (used by internal background worker)."""
        stmt = select(Reminder).where(Reminder.id == reminder_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, reminder: Reminder) -> Reminder:
        """Persist a new reminder."""
        self.session.add(reminder)
        await self.session.commit()
        await self.session.refresh(reminder)
        return reminder

    async def update(self, reminder: Reminder) -> Reminder:
        """Commit updates to an existing reminder."""
        await self.session.commit()
        await self.session.refresh(reminder)
        return reminder

    async def delete(self, reminder: Reminder) -> None:
        """Physically delete a reminder record."""
        await self.session.delete(reminder)
        await self.session.commit()

    async def list_reminders(
        self,
        user_id: uuid.UUID,
        status: ReminderStatus | None = None,
        task_id: uuid.UUID | None = None,
        schedule_id: uuid.UUID | None = None,
        duty_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Reminder], int]:
        """List reminders belonging to user with filtering and pagination."""
        query = select(Reminder).where(Reminder.user_id == user_id)

        if status is not None:
            query = query.where(Reminder.status == status)

        if task_id is not None:
            query = query.where(Reminder.task_id == task_id)

        if schedule_id is not None:
            query = query.where(Reminder.schedule_id == schedule_id)

        if duty_id is not None:
            query = query.where(Reminder.duty_id == duty_id)

        count_stmt = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(Reminder.remind_at.asc()).offset(offset).limit(page_size)

        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def get_all_pending_future_reminders(self, now: datetime) -> list[Reminder]:
        """Retrieve all pending future reminders for scheduler rebuild."""
        stmt = select(Reminder).where(
            Reminder.status == ReminderStatus.PENDING,
            Reminder.remind_at >= now,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
