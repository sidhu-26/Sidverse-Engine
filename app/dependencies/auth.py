from fastapi import Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AppException
from app.models.user import User
from app.services.auth_service import AuthService

settings = get_settings()


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency that extracts and validates the authenticated user
    from session cookie or Authorization header.
    """
    auth_service = AuthService(db)

    # 1. Try extracting token from HttpOnly cookie
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)

    # 2. Fallback to Authorization: Bearer <token>
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ").strip()

    if not token:
        raise AppException(
            message="Authentication credentials were not provided.",
            code="NOT_AUTHENTICATED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user = await auth_service.get_user_from_session(token)
    if not user:
        raise AppException(
            message="Invalid or expired session.",
            code="INVALID_SESSION",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        raise AppException(
            message="This user account has been deactivated.",
            code="USER_INACTIVE",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return user
