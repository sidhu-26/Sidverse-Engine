import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
