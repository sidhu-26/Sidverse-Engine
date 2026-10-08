"""FastAPI common dependencies package."""

from app.core.database import get_db

__all__ = ["get_db"]
