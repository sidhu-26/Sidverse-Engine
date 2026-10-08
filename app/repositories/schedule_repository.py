import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ScheduleStatus
from app.models.schedule import Schedule


class ScheduleRepository:
    """Data access repository for Schedule domain entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id_and_user(
        self,
        schedule_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Schedule | None:
        """Fetch an active (non-deleted) schedule for the user."""
        stmt = select(Schedule).where(
            Schedule.id == schedule_id,
            Schedule.user_id == user_id,
            Schedule.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, schedule: Schedule) -> Schedule:
        """Persist a new schedule."""
        self.session.add(schedule)
        await self.session.commit()
        await self.session.refresh(schedule)
        return schedule

    async def update(self, schedule: Schedule) -> Schedule:
        """Commit changes to an existing schedule."""
        await self.session.commit()
        await self.session.refresh(schedule)
        return schedule

    async def soft_delete(self, schedule: Schedule) -> None:
        """Soft-delete a schedule."""
        schedule.deleted_at = datetime.now(UTC)
        await self.session.commit()

    async def find_overlapping(
        self,
        user_id: uuid.UUID,
        start_at: datetime,
        end_at: datetime,
        exclude_id: uuid.UUID | None = None,
    ) -> list[Schedule]:
        """Find non-cancelled, active schedules that overlap with the given time range."""
        stmt = select(Schedule).where(
            Schedule.user_id == user_id,
            Schedule.deleted_at.is_(None),
            Schedule.status != ScheduleStatus.CANCELLED,
            Schedule.start_at < end_at,
            Schedule.end_at > start_at,
        )
        if exclude_id is not None:
            stmt = stmt.where(Schedule.id != exclude_id)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

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
    ) -> tuple[list[Schedule], int]:
        """List user schedules with filtering and pagination."""
        query = select(Schedule).where(
            Schedule.user_id == user_id,
            Schedule.deleted_at.is_(None),
        )

        if status is not None:
            query = query.where(Schedule.status == status)

        if task_id is not None:
            query = query.where(Schedule.task_id == task_id)

        if start_after is not None:
            query = query.where(Schedule.start_at >= start_after)

        if start_before is not None:
            query = query.where(Schedule.start_at <= start_before)

        if end_after is not None:
            query = query.where(Schedule.end_at >= end_after)

        if end_before is not None:
            query = query.where(Schedule.end_at <= end_before)

        if search and search.strip():
            pattern = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Schedule.title.ilike(pattern),
                    Schedule.description.ilike(pattern),
                )
            )

        # Total count
        count_stmt = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # Pagination and order
        offset = (page - 1) * page_size
        query = query.order_by(Schedule.start_at.asc(), Schedule.created_at.desc())
        query = query.offset(offset).limit(page_size)

        result = await self.session.execute(query)
        return list(result.scalars().all()), total
