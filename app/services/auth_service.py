from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.models.user import User
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository


class AuthService:
    """Authentication and session management business logic."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.session_repo = SessionRepository(db)
        self.settings = get_settings()

    async def register(
        self,
        email: str,
        display_name: str,
        password: str,
        timezone_str: str = "Asia/Kolkata",
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[User, str]:
        """Register a new user, hash password with Argon2id, and create an active session."""
        normalized_email = email.strip().lower()

        # Check for existing email
        existing_user = await self.user_repo.get_by_email(normalized_email)
        if existing_user:
            raise AppException(
                message="An account with this email already exists.",
                code="EMAIL_ALREADY_EXISTS",
                status_code=409,
            )

        hashed_pw = hash_password(password)
        user = await self.user_repo.create(
            email=normalized_email,
            display_name=display_name,
            password_hash=hashed_pw,
            timezone=timezone_str,
        )

        raw_token, _ = await self._create_user_session(user.id, user_agent, ip_address)
        return user, raw_token

    async def authenticate(
        self,
        email: str,
        password: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[User, str]:
        """Verify user credentials with Argon2id and issue a new session token."""
        normalized_email = email.strip().lower()
        user = await self.user_repo.get_by_email(normalized_email)

        # Constant-time mitigation / unified error without revealing user existence
        if not user or not verify_password(password, user.password_hash):
            raise AppException(
                message="Invalid email or password.",
                code="INVALID_CREDENTIALS",
                status_code=401,
            )

        if not user.is_active:
            raise AppException(
                message="This user account has been deactivated.",
                code="USER_INACTIVE",
                status_code=403,
            )

        raw_token, _ = await self._create_user_session(user.id, user_agent, ip_address)
        return user, raw_token

    async def get_user_from_session(self, raw_token: str) -> User | None:
        """Validate raw session token and return active User."""
        if not raw_token:
            return None
        token_hash = hash_session_token(raw_token)
        session = await self.session_repo.get_active_session(token_hash)
        if not session or not session.user or not session.user.is_active:
            return None
        return session.user

    async def logout(self, raw_token: str | None) -> None:
        """Revoke active session token."""
        if not raw_token:
            return
        token_hash = hash_session_token(raw_token)
        await self.session_repo.revoke_session(token_hash)

    async def _create_user_session(
        self,
        user_id: object,
        user_agent: str | None,
        ip_address: str | None,
    ) -> tuple[str, datetime]:
        """Internal helper to create a session token and store its hash in the database."""
        raw_token = generate_session_token()
        token_hash = hash_session_token(raw_token)
        expires_at = datetime.now(UTC) + timedelta(seconds=self.settings.SESSION_EXPIRE_SECONDS)

        await self.session_repo.create_session(
            user_id=user_id,  # type: ignore[arg-type]
            session_token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        return raw_token, expires_at
