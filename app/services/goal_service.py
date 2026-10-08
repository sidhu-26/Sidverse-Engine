import math
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.enums import ActivityAction, GoalStatus
from app.models.goal import Goal, GoalMilestone
from app.repositories.activity_repository import ActivityRepository
from app.repositories.goal_repository import GoalRepository
from app.repositories.milestone_repository import MilestoneRepository
from app.schemas.goal import (
    GoalCreate,
    GoalListResponse,
    GoalMilestoneCreate,
    GoalMilestoneResponse,
    GoalMilestoneUpdate,
    GoalResponse,
    GoalUpdate,
)


class GoalService:
    """Business service governing Goals and nested milestone progress checkpoints."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.goal_repo = GoalRepository(db)
        self.milestone_repo = MilestoneRepository(db)
        self.activity_repo = ActivityRepository(db)

    # ============================================================
    # Goals
    # ============================================================

    async def create_goal(
        self,
        user_id: uuid.UUID,
        data: GoalCreate,
    ) -> GoalResponse:
        """Create a new goal scoped to the user."""
        goal = Goal(
            user_id=user_id,
            title=data.title,
            description=data.description,
            status=data.status,
            target_date=data.target_date,
            progress=data.progress,
        )
        created = await self.goal_repo.create(goal)

        await self.activity_repo.log_activity(
            user_id=user_id,
            entity_type="GOAL",
            entity_id=created.id,
            action=ActivityAction.GOAL_CREATED,
            metadata={
                "title": created.title,
                "status": created.status.value,
                "progress": created.progress,
            },
        )

        return self._to_response(created)

    async def get_goal(
        self,
        goal_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> GoalResponse:
        """Fetch goal detail including milestones."""
        goal = await self.goal_repo.get_by_id_and_user(goal_id, user_id, load_milestones=True)
        if not goal:
            raise AppException(
                message="Goal not found.",
                code="GOAL_NOT_FOUND",
                status_code=404,
            )
        return self._to_response(goal)

    async def list_goals(
        self,
        user_id: uuid.UUID,
        status: GoalStatus | None = None,
        search: str | None = None,
        target_before: datetime | None = None,
        target_after: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> GoalListResponse:
        """List active user goals with pagination and optional filters."""
        items, total = await self.goal_repo.list_goals(
            user_id=user_id,
            status=status,
            search=search,
            target_before=target_before,
            target_after=target_after,
            page=page,
            page_size=page_size,
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return GoalListResponse(
            items=[self._to_response(g) for g in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def update_goal(
        self,
        goal_id: uuid.UUID,
        user_id: uuid.UUID,
        data: GoalUpdate,
    ) -> GoalResponse:
        """Update goal attributes and log activities."""
        goal = await self.goal_repo.get_by_id_and_user(goal_id, user_id, load_milestones=True)
        if not goal:
            raise AppException(
                message="Goal not found.",
                code="GOAL_NOT_FOUND",
                status_code=404,
            )

        changes: dict[str, dict[str, str | int | None]] = {}
        old_status = goal.status

        if data.title is not None and data.title != goal.title:
            changes["title"] = {"old": goal.title, "new": data.title}
            goal.title = data.title

        if data.description is not None and data.description != goal.description:
            changes["description"] = {"old": goal.description, "new": data.description}
            goal.description = data.description

        if data.progress is not None and data.progress != goal.progress:
            changes["progress"] = {"old": goal.progress, "new": data.progress}
            goal.progress = data.progress

        if data.target_date is not None and data.target_date != goal.target_date:
            changes["target_date"] = {
                "old": goal.target_date.isoformat() if goal.target_date else None,
                "new": data.target_date.isoformat(),
            }
            goal.target_date = data.target_date

        if data.status is not None and data.status != old_status:
            goal.status = data.status
            if data.status == GoalStatus.COMPLETED:
                await self.activity_repo.log_activity(
                    user_id=user_id,
                    entity_type="GOAL",
                    entity_id=goal.id,
                    action=ActivityAction.GOAL_COMPLETED,
                    metadata={"old_status": old_status.value, "new_status": data.status.value},
                )
            else:
                changes["status"] = {"old": old_status.value, "new": data.status.value}

        if changes:
            await self.activity_repo.log_activity(
                user_id=user_id,
                entity_type="GOAL",
                entity_id=goal.id,
                action=ActivityAction.GOAL_UPDATED,
                metadata={"changes": changes},
            )

        updated = await self.goal_repo.update(goal)
        return self._to_response(updated)

    async def delete_goal(
        self,
        goal_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Soft delete a goal."""
        goal = await self.goal_repo.get_by_id_and_user(goal_id, user_id, load_milestones=False)
        if not goal:
            raise AppException(
                message="Goal not found.",
                code="GOAL_NOT_FOUND",
                status_code=404,
            )

        await self.goal_repo.soft_delete(goal)

        await self.activity_repo.log_activity(
            user_id=user_id,
            entity_type="GOAL",
            entity_id=goal.id,
            action=ActivityAction.GOAL_DELETED,
            metadata={"title": goal.title},
        )

    # ============================================================
    # Milestones
    # ============================================================

    async def create_milestone(
        self,
        goal_id: uuid.UUID,
        user_id: uuid.UUID,
        data: GoalMilestoneCreate,
    ) -> GoalMilestoneResponse:
        """Add a milestone to an active goal."""
        goal = await self.goal_repo.get_by_id_and_user(goal_id, user_id, load_milestones=False)
        if not goal:
            raise AppException(
                message="Goal not found or has been deleted.",
                code="GOAL_NOT_FOUND",
                status_code=404,
            )

        milestone = GoalMilestone(
            goal_id=goal.id,
            title=data.title,
            description=data.description,
            position=data.position,
            is_completed=False,
            completed_at=None,
        )
        created = await self.milestone_repo.create(milestone)
        return GoalMilestoneResponse.model_validate(created)

    async def list_milestones(
        self,
        goal_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[GoalMilestoneResponse]:
        """List all milestones for a goal ordered by position."""
        goal = await self.goal_repo.get_by_id_and_user(goal_id, user_id, load_milestones=False)
        if not goal:
            raise AppException(
                message="Goal not found.",
                code="GOAL_NOT_FOUND",
                status_code=404,
            )
        milestones = await self.milestone_repo.list_by_goal(goal_id)
        return [GoalMilestoneResponse.model_validate(m) for m in milestones]

    async def get_milestone(
        self,
        goal_id: uuid.UUID,
        milestone_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> GoalMilestoneResponse:
        """Fetch single milestone."""
        goal = await self.goal_repo.get_by_id_and_user(goal_id, user_id, load_milestones=False)
        if not goal:
            raise AppException(
                message="Goal not found.",
                code="GOAL_NOT_FOUND",
                status_code=404,
            )
        milestone = await self.milestone_repo.get_by_id_and_goal(milestone_id, goal_id)
        if not milestone:
            raise AppException(
                message="Milestone not found.",
                code="MILESTONE_NOT_FOUND",
                status_code=404,
            )
        return GoalMilestoneResponse.model_validate(milestone)

    async def update_milestone(
        self,
        goal_id: uuid.UUID,
        milestone_id: uuid.UUID,
        user_id: uuid.UUID,
        data: GoalMilestoneUpdate,
    ) -> GoalMilestoneResponse:
        """Update milestone details and handle completion timestamps/activities."""
        goal = await self.goal_repo.get_by_id_and_user(goal_id, user_id, load_milestones=False)
        if not goal:
            raise AppException(
                message="Goal not found.",
                code="GOAL_NOT_FOUND",
                status_code=404,
            )
        milestone = await self.milestone_repo.get_by_id_and_goal(milestone_id, goal_id)
        if not milestone:
            raise AppException(
                message="Milestone not found.",
                code="MILESTONE_NOT_FOUND",
                status_code=404,
            )

        if data.title is not None:
            milestone.title = data.title

        if data.description is not None:
            milestone.description = data.description

        if data.position is not None:
            milestone.position = data.position

        if data.is_completed is not None and data.is_completed != milestone.is_completed:
            milestone.is_completed = data.is_completed
            if data.is_completed:
                milestone.completed_at = datetime.now(UTC)
                await self.activity_repo.log_activity(
                    user_id=user_id,
                    entity_type="GOAL_MILESTONE",
                    entity_id=milestone.id,
                    action=ActivityAction.GOAL_MILESTONE_COMPLETED,
                    metadata={"title": milestone.title, "goal_id": str(goal_id)},
                )
            else:
                milestone.completed_at = None
                await self.activity_repo.log_activity(
                    user_id=user_id,
                    entity_type="GOAL_MILESTONE",
                    entity_id=milestone.id,
                    action=ActivityAction.GOAL_MILESTONE_REOPENED,
                    metadata={"title": milestone.title, "goal_id": str(goal_id)},
                )

        updated = await self.milestone_repo.update(milestone)
        return GoalMilestoneResponse.model_validate(updated)

    async def delete_milestone(
        self,
        goal_id: uuid.UUID,
        milestone_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Delete milestone from goal."""
        goal = await self.goal_repo.get_by_id_and_user(goal_id, user_id, load_milestones=False)
        if not goal:
            raise AppException(
                message="Goal not found.",
                code="GOAL_NOT_FOUND",
                status_code=404,
            )
        milestone = await self.milestone_repo.get_by_id_and_goal(milestone_id, goal_id)
        if not milestone:
            raise AppException(
                message="Milestone not found.",
                code="MILESTONE_NOT_FOUND",
                status_code=404,
            )
        await self.milestone_repo.delete(milestone)

    def _to_response(self, goal: Goal) -> GoalResponse:
        """Safely serialize Goal entity into GoalResponse checking for loaded milestones."""
        from sqlalchemy import inspect

        milestones: list[GoalMilestoneResponse] = []
        state = inspect(goal)
        if "milestones" in state.dict and goal.milestones is not None:
            milestones = [GoalMilestoneResponse.model_validate(m) for m in goal.milestones]

        return GoalResponse(
            id=goal.id,
            user_id=goal.user_id,
            title=goal.title,
            description=goal.description,
            status=goal.status,
            target_date=goal.target_date,
            progress=goal.progress,
            created_at=goal.created_at,
            updated_at=goal.updated_at,
            milestones=milestones,
        )
