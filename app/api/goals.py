import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.enums import GoalStatus
from app.models.user import User
from app.schemas.goal import (
    GoalCreate,
    GoalListResponse,
    GoalMilestoneCreate,
    GoalMilestoneResponse,
    GoalMilestoneUpdate,
    GoalResponse,
    GoalUpdate,
)
from app.services.goal_service import GoalService

router = APIRouter(prefix="/goals", tags=["Goals"])


# ============================================================
# Goal Endpoints
# ============================================================


@router.post(
    "",
    response_model=GoalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Goal",
    description="Create a new long-term goal.",
)
async def create_goal(
    body: GoalCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoalResponse:
    goal_service = GoalService(db)
    return await goal_service.create_goal(user_id=current_user.id, data=body)


@router.get(
    "",
    response_model=GoalListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Goals",
    description="Retrieve paginated goals belonging to current user.",
)
async def list_goals(
    status_filter: GoalStatus | None = Query(
        default=None, alias="status", description="Filter by status"
    ),
    search: str | None = Query(default=None, description="Search keyword in title or description"),
    target_before: datetime | None = Query(
        default=None, description="Filter target date on or before"
    ),
    target_after: datetime | None = Query(
        default=None, description="Filter target date on or after"
    ),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoalListResponse:
    goal_service = GoalService(db)
    return await goal_service.list_goals(
        user_id=current_user.id,
        status=status_filter,
        search=search,
        target_before=target_before,
        target_after=target_after,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{goal_id}",
    response_model=GoalResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Goal Detail",
    description="Retrieve goal details including all milestones.",
)
async def get_goal(
    goal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoalResponse:
    goal_service = GoalService(db)
    return await goal_service.get_goal(goal_id=goal_id, user_id=current_user.id)


@router.patch(
    "/{goal_id}",
    response_model=GoalResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Goal",
    description="Update goal attributes or progress (0-100).",
)
async def update_goal(
    goal_id: uuid.UUID,
    body: GoalUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoalResponse:
    goal_service = GoalService(db)
    return await goal_service.update_goal(
        goal_id=goal_id,
        user_id=current_user.id,
        data=body,
    )


@router.delete(
    "/{goal_id}",
    status_code=status.HTTP_200_OK,
    summary="Soft Delete Goal",
    description="Soft-delete a goal.",
)
async def delete_goal(
    goal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    goal_service = GoalService(db)
    await goal_service.delete_goal(goal_id=goal_id, user_id=current_user.id)
    return {"message": "Goal deleted successfully."}


# ============================================================
# Milestone Endpoints
# ============================================================


@router.post(
    "/{goal_id}/milestones",
    response_model=GoalMilestoneResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Milestone",
    description="Add a milestone progress checkpoint to a goal.",
)
async def create_milestone(
    goal_id: uuid.UUID,
    body: GoalMilestoneCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoalMilestoneResponse:
    goal_service = GoalService(db)
    return await goal_service.create_milestone(
        goal_id=goal_id,
        user_id=current_user.id,
        data=body,
    )


@router.get(
    "/{goal_id}/milestones",
    response_model=list[GoalMilestoneResponse],
    status_code=status.HTTP_200_OK,
    summary="List Milestones",
    description="List all milestones for a goal ordered by position.",
)
async def list_milestones(
    goal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GoalMilestoneResponse]:
    goal_service = GoalService(db)
    return await goal_service.list_milestones(goal_id=goal_id, user_id=current_user.id)


@router.get(
    "/{goal_id}/milestones/{milestone_id}",
    response_model=GoalMilestoneResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Milestone Detail",
    description="Retrieve a single milestone detail.",
)
async def get_milestone(
    goal_id: uuid.UUID,
    milestone_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoalMilestoneResponse:
    goal_service = GoalService(db)
    return await goal_service.get_milestone(
        goal_id=goal_id,
        milestone_id=milestone_id,
        user_id=current_user.id,
    )


@router.patch(
    "/{goal_id}/milestones/{milestone_id}",
    response_model=GoalMilestoneResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Milestone",
    description="Update milestone title, position, or completion status.",
)
async def update_milestone(
    goal_id: uuid.UUID,
    milestone_id: uuid.UUID,
    body: GoalMilestoneUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoalMilestoneResponse:
    goal_service = GoalService(db)
    return await goal_service.update_milestone(
        goal_id=goal_id,
        milestone_id=milestone_id,
        user_id=current_user.id,
        data=body,
    )


@router.delete(
    "/{goal_id}/milestones/{milestone_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Milestone",
    description="Delete a milestone checkpoint.",
)
async def delete_milestone(
    goal_id: uuid.UUID,
    milestone_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    goal_service = GoalService(db)
    await goal_service.delete_milestone(
        goal_id=goal_id,
        milestone_id=milestone_id,
        user_id=current_user.id,
    )
    return {"message": "Milestone deleted successfully."}
