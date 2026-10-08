import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import GoalStatus
from app.models.goal import Goal


class GoalRepository:
    """Repository for Goal domain entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id_and_user(
        self,
        goal_id: uuid.UUID,
        user_id: uuid.UUID,
        load_milestones: bool = True,
    ) -> Goal | None:
        """Fetch active goal with its milestones."""
        stmt = select(Goal).where(
            Goal.id == goal_id,
            Goal.user_id == user_id,
            Goal.deleted_at.is_(None),
        )
        if load_milestones:
            stmt = stmt.options(selectinload(Goal.milestones))

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, goal: Goal) -> Goal:
        """Persist a new goal."""
        self.session.add(goal)
        await self.session.commit()
        await self.session.refresh(goal)
        return goal

    async def update(self, goal: Goal) -> Goal:
        """Update and commit goal."""
        await self.session.commit()
        await self.session.refresh(goal)
        return goal

    async def soft_delete(self, goal: Goal) -> None:
        """Soft delete a goal."""
        goal.deleted_at = datetime.now(UTC)
        await self.session.commit()

    async def list_goals(
        self,
        user_id: uuid.UUID,
        status: GoalStatus | None = None,
        search: str | None = None,
        target_before: datetime | None = None,
        target_after: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Goal], int]:
        """List active goals with pagination and optional filters."""
        query = (
            select(Goal)
            .options(selectinload(Goal.milestones))
            .where(
                Goal.user_id == user_id,
                Goal.deleted_at.is_(None),
            )
        )

        if status is not None:
            query = query.where(Goal.status == status)

        if target_before is not None:
            query = query.where(Goal.target_date <= target_before)

        if target_after is not None:
            query = query.where(Goal.target_date >= target_after)

        if search and search.strip():
            pattern = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Goal.title.ilike(pattern),
                    Goal.description.ilike(pattern),
                )
            )

        count_stmt = select(func.count()).select_from(
            select(Goal.id)
            .where(
                Goal.user_id == user_id,
                Goal.deleted_at.is_(None),
            )
            .subquery()
        )
        total = (await self.session.execute(count_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(Goal.created_at.desc()).offset(offset).limit(page_size)

        result = await self.session.execute(query)
        return list(result.scalars().all()), total
