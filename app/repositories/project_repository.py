import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ProjectPriority, ProjectStatus
from app.models.project import Project


class ProjectRepository:
    """Repository for Project domain entity operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id_and_user(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Project | None:
        """Fetch an active (non-deleted) project belonging to a specific user."""
        stmt = select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id,
            Project.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, project: Project) -> Project:
        """Persist a new project."""
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def update(self, project: Project) -> Project:
        """Update and commit project entity."""
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def soft_delete(self, project: Project) -> None:
        """Soft delete a project."""
        project.deleted_at = datetime.now(UTC)
        await self.session.commit()

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
    ) -> tuple[list[Project], int]:
        """List active projects belonging to user with filtering and pagination."""
        query = select(Project).where(
            Project.user_id == user_id,
            Project.deleted_at.is_(None),
        )

        if status is not None:
            query = query.where(Project.status == status)

        if priority is not None:
            query = query.where(Project.priority == priority)

        if target_before is not None:
            query = query.where(Project.target_date <= target_before)

        if target_after is not None:
            query = query.where(Project.target_date >= target_after)

        if search and search.strip():
            pattern = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Project.name.ilike(pattern),
                    Project.description.ilike(pattern),
                )
            )

        count_stmt = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(Project.created_at.desc()).offset(offset).limit(page_size)

        result = await self.session.execute(query)
        return list(result.scalars().all()), total
