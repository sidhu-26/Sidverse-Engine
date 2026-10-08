import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TaskPriority, TaskStatus
from app.models.task import Task


class TaskRepository:
    """Repository for Task entity operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id_and_user(
        self,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Task | None:
        """Fetch an active (non-deleted) task belonging to a specific user."""
        stmt = select(Task).where(
            Task.id == task_id,
            Task.user_id == user_id,
            Task.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, task: Task) -> Task:
        """Persist a new task entity."""
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def update(self, task: Task) -> Task:
        """Update and persist an existing task."""
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def soft_delete(self, task: Task) -> None:
        """Mark task as soft-deleted."""
        task.deleted_at = datetime.now(UTC)
        await self.session.commit()

    async def list_tasks(
        self,
        user_id: uuid.UUID,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        project_id: uuid.UUID | None = None,
        overdue: bool | None = None,
        due_before: datetime | None = None,
        due_after: datetime | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Task], int]:
        """List tasks belonging to user with optional filtering and pagination."""
        query = select(Task).where(
            Task.user_id == user_id,
            Task.deleted_at.is_(None),
        )

        if status is not None:
            query = query.where(Task.status == status)

        if priority is not None:
            query = query.where(Task.priority == priority)

        if project_id is not None:
            query = query.where(Task.project_id == project_id)

        now = datetime.now(UTC)
        if overdue is True:
            query = query.where(
                Task.due_at.is_not(None),
                Task.due_at < now,
                Task.status.not_in([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
            )
        elif overdue is False:
            query = query.where(
                or_(
                    Task.due_at.is_(None),
                    Task.due_at >= now,
                    Task.status.in_([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
                )
            )

        if due_before is not None:
            query = query.where(Task.due_at <= due_before)

        if due_after is not None:
            query = query.where(Task.due_at >= due_after)

        if search and search.strip():
            search_pattern = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Task.title.ilike(search_pattern),
                    Task.description.ilike(search_pattern),
                )
            )

        # Count total matching records
        count_stmt = select(func.count()).select_from(query.subquery())
        total_count = (await self.session.execute(count_stmt)).scalar() or 0

        # Apply ordering and pagination
        offset = (page - 1) * page_size
        query = (
            query.order_by(Task.due_at.asc().nulls_last(), Task.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )

        result = await self.session.execute(query)
        items = list(result.scalars().all())
        return items, total_count
