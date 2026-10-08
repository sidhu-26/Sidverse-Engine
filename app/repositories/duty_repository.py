import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.duty import Duty


class DutyRepository:
    """Repository for querying Duty domain entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id_and_user(
        self,
        duty_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Duty | None:
        """Fetch active non-deleted duty belonging to user."""
        stmt = select(Duty).where(
            Duty.id == duty_id,
            Duty.user_id == user_id,
            Duty.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
