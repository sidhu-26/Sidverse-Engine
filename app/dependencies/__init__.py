"""FastAPI common dependencies package."""

from app.core.database import get_db
from app.dependencies.auth import get_current_user

__all__ = [
    "get_db",
    "get_current_user",
]
