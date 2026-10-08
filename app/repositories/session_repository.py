import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.session import UserSession


class SessionRepository:
    """Repository for UserSession database operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_session(
        self,
        user_id: uuid.UUID,
        session_token_hash: str,
        expires_at: datetime,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> UserSession:
        """Create and persist a new user session."""
        user_session = UserSession(
            user_id=user_id,
            session_token_hash=session_token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
            is_revoked=False,
        )
        self.session.add(user_session)
        await self.session.commit()
        await self.session.refresh(user_session)
        return user_session

    async def get_active_session(self, session_token_hash: str) -> UserSession | None:
        """Fetch an active, non-expired, non-revoked session with its associated user."""
        now = datetime.now(UTC)
        stmt = (
            select(UserSession)
            .options(selectinload(UserSession.user))
            .where(
                UserSession.session_token_hash == session_token_hash,
                UserSession.is_revoked.is_(False),
                UserSession.expires_at > now,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_session(self, session_token_hash: str) -> bool:
        """Mark a session as revoked."""
        stmt = (
            update(UserSession)
            .where(
                UserSession.session_token_hash == session_token_hash,
                UserSession.is_revoked.is_(False),
            )
            .values(is_revoked=True)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0
