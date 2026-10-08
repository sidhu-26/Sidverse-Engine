import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.goal import GoalMilestone


class MilestoneRepository:
    """Repository for GoalMilestone domain entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id_and_goal(
        self,
        milestone_id: uuid.UUID,
        goal_id: uuid.UUID,
    ) -> GoalMilestone | None:
        """Fetch milestone belonging to a specific goal."""
        stmt = select(GoalMilestone).where(
            GoalMilestone.id == milestone_id,
            GoalMilestone.goal_id == goal_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, milestone: GoalMilestone) -> GoalMilestone:
        """Persist a new milestone."""
        self.session.add(milestone)
        await self.session.commit()
        await self.session.refresh(milestone)
        return milestone

    async def update(self, milestone: GoalMilestone) -> GoalMilestone:
        """Commit changes to an existing milestone."""
        await self.session.commit()
        await self.session.refresh(milestone)
        return milestone

    async def delete(self, milestone: GoalMilestone) -> None:
        """Physically delete a milestone."""
        await self.session.delete(milestone)
        await self.session.commit()

    async def list_by_goal(self, goal_id: uuid.UUID) -> list[GoalMilestone]:
        """List all milestones for a goal ordered by position ASC, then created_at ASC."""
        stmt = (
            select(GoalMilestone)
            .where(GoalMilestone.goal_id == goal_id)
            .order_by(GoalMilestone.position.asc(), GoalMilestone.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
