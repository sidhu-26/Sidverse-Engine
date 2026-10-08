import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.enums import TaskPriority, TaskStatus
from app.models.user import User
from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse, TaskUpdate
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Task",
    description="Create a new personal task belonging to the authenticated user.",
)
async def create_task(
    body: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    task_service = TaskService(db)
    return await task_service.create_task(user_id=current_user.id, data=body)


@router.get(
    "",
    response_model=TaskListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Tasks",
    description="Retrieve a paginated list of tasks belonging to the authenticated user.",
)
async def list_tasks(
    status_filter: TaskStatus | None = Query(
        default=None, alias="status", description="Filter by task status"
    ),
    priority_filter: TaskPriority | None = Query(
        default=None, alias="priority", description="Filter by task priority"
    ),
    project_id: uuid.UUID | None = Query(
        default=None, description="Filter by associated project UUID"
    ),
    overdue: bool | None = Query(default=None, description="Filter overdue tasks"),
    due_before: datetime | None = Query(
        default=None, description="Filter tasks due on or before timestamp"
    ),
    due_after: datetime | None = Query(
        default=None, description="Filter tasks due on or after timestamp"
    ),
    search: str | None = Query(default=None, description="Search keyword in title or description"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskListResponse:
    task_service = TaskService(db)
    return await task_service.list_tasks(
        user_id=current_user.id,
        status=status_filter,
        priority=priority_filter,
        project_id=project_id,
        overdue=overdue,
        due_before=due_before,
        due_after=due_after,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Task Detail",
    description="Retrieve the details of a specific task belonging to the authenticated user.",
)
async def get_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    task_service = TaskService(db)
    return await task_service.get_task(task_id=task_id, user_id=current_user.id)


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Task",
    description="Partially update a task and enforce status transition rules.",
)
async def update_task(
    task_id: uuid.UUID,
    body: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    task_service = TaskService(db)
    return await task_service.update_task(
        task_id=task_id,
        user_id=current_user.id,
        data=body,
    )


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_200_OK,
    summary="Soft Delete Task",
    description="Soft-delete a task and record the deletion in the audit trail.",
)
async def delete_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    task_service = TaskService(db)
    await task_service.delete_task(task_id=task_id, user_id=current_user.id)
    return {"message": "Task deleted successfully."}
