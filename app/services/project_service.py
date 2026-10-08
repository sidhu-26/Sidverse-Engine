import math
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.enums import ActivityAction, ProjectPriority, ProjectStatus
from app.models.project import Project
from app.repositories.activity_repository import ActivityRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)


class ProjectService:
    """Business service governing Project lifecycle and organization rules."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.project_repo = ProjectRepository(db)
        self.activity_repo = ActivityRepository(db)

    async def create_project(
        self,
        user_id: uuid.UUID,
        data: ProjectCreate,
    ) -> ProjectResponse:
        """Create a new project scoped to the authenticated user."""
        project = Project(
            user_id=user_id,
            name=data.name,
            description=data.description,
            status=data.status,
            priority=data.priority,
            target_date=data.target_date,
        )
        created = await self.project_repo.create(project)

        await self.activity_repo.log_activity(
            user_id=user_id,
            entity_type="PROJECT",
            entity_id=created.id,
            action=ActivityAction.PROJECT_CREATED,
            metadata={
                "name": created.name,
                "status": created.status.value,
                "priority": created.priority.value,
            },
        )

        return ProjectResponse.model_validate(created)

    async def get_project(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ProjectResponse:
        """Fetch project detail for authenticated user."""
        project = await self.project_repo.get_by_id_and_user(project_id, user_id)
        if not project:
            raise AppException(
                message="Project not found.",
                code="PROJECT_NOT_FOUND",
                status_code=404,
            )
        return ProjectResponse.model_validate(project)

    async def list_projects(
        self,
        user_id: uuid.UUID,
        status: ProjectStatus | None = None,
        priority: ProjectPriority | None = None,
        search: str | None = None,
        target_before: datetime | None = None,
        target_after: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ProjectListResponse:
        """List active user projects with filtering and pagination."""
        items, total = await self.project_repo.list_projects(
            user_id=user_id,
            status=status,
            priority=priority,
            search=search,
            target_before=target_before,
            target_after=target_after,
            page=page,
            page_size=page_size,
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return ProjectListResponse(
            items=[ProjectResponse.model_validate(p) for p in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def update_project(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        data: ProjectUpdate,
    ) -> ProjectResponse:
        """Update project attributes and record audit logs."""
        project = await self.project_repo.get_by_id_and_user(project_id, user_id)
        if not project:
            raise AppException(
                message="Project not found.",
                code="PROJECT_NOT_FOUND",
                status_code=404,
            )

        changes: dict[str, dict[str, str | None]] = {}
        old_status = project.status

        if data.name is not None and data.name != project.name:
            changes["name"] = {"old": project.name, "new": data.name}
            project.name = data.name

        if data.description is not None and data.description != project.description:
            changes["description"] = {"old": project.description, "new": data.description}
            project.description = data.description

        if data.priority is not None and data.priority != project.priority:
            changes["priority"] = {"old": project.priority.value, "new": data.priority.value}
            project.priority = data.priority

        if data.target_date is not None and data.target_date != project.target_date:
            changes["target_date"] = {
                "old": project.target_date.isoformat() if project.target_date else None,
                "new": data.target_date.isoformat(),
            }
            project.target_date = data.target_date

        if data.status is not None and data.status != old_status:
            project.status = data.status
            if data.status == ProjectStatus.COMPLETED:
                await self.activity_repo.log_activity(
                    user_id=user_id,
                    entity_type="PROJECT",
                    entity_id=project.id,
                    action=ActivityAction.PROJECT_COMPLETED,
                    metadata={"old_status": old_status.value, "new_status": data.status.value},
                )
            else:
                changes["status"] = {"old": old_status.value, "new": data.status.value}

        if changes:
            await self.activity_repo.log_activity(
                user_id=user_id,
                entity_type="PROJECT",
                entity_id=project.id,
                action=ActivityAction.PROJECT_UPDATED,
                metadata={"changes": changes},
            )

        updated = await self.project_repo.update(project)
        return ProjectResponse.model_validate(updated)

    async def delete_project(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Soft delete project."""
        project = await self.project_repo.get_by_id_and_user(project_id, user_id)
        if not project:
            raise AppException(
                message="Project not found.",
                code="PROJECT_NOT_FOUND",
                status_code=404,
            )

        await self.project_repo.soft_delete(project)

        await self.activity_repo.log_activity(
            user_id=user_id,
            entity_type="PROJECT",
            entity_id=project.id,
            action=ActivityAction.PROJECT_DELETED,
            metadata={"name": project.name},
        )
