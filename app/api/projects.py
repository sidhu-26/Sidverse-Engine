import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.enums import ProjectPriority, ProjectStatus
from app.models.user import User
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Project",
    description="Create a new project workspace for the authenticated user.",
)
async def create_project(
    body: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    project_service = ProjectService(db)
    return await project_service.create_project(user_id=current_user.id, data=body)


@router.get(
    "",
    response_model=ProjectListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Projects",
    description="Retrieve paginated list of active projects belonging to current user.",
)
async def list_projects(
    status_filter: ProjectStatus | None = Query(
        default=None, alias="status", description="Filter by project status"
    ),
    priority_filter: ProjectPriority | None = Query(
        default=None, alias="priority", description="Filter by project priority"
    ),
    search: str | None = Query(
        default=None, description="Search keyword in project name or description"
    ),
    target_before: datetime | None = Query(
        default=None, description="Filter projects with target date before"
    ),
    target_after: datetime | None = Query(
        default=None, description="Filter projects with target date after"
    ),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectListResponse:
    project_service = ProjectService(db)
    return await project_service.list_projects(
        user_id=current_user.id,
        status=status_filter,
        priority=priority_filter,
        search=search,
        target_before=target_before,
        target_after=target_after,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Project Detail",
    description="Retrieve specific project details.",
)
async def get_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    project_service = ProjectService(db)
    return await project_service.get_project(project_id=project_id, user_id=current_user.id)


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Project",
    description="Update project details and status.",
)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    project_service = ProjectService(db)
    return await project_service.update_project(
        project_id=project_id,
        user_id=current_user.id,
        data=body,
    )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_200_OK,
    summary="Soft Delete Project",
    description="Soft-delete a project.",
)
async def delete_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    project_service = ProjectService(db)
    await project_service.delete_project(project_id=project_id, user_id=current_user.id)
    return {"message": "Project deleted successfully."}
