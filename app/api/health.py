import logging
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

logger = logging.getLogger("sid_os.health")
router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "",
    summary="Application Health Check",
    description="Verifies that the FastAPI application is up and running.",
    status_code=status.HTTP_200_OK,
)
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/db",
    summary="Database Health Check",
    description="Verifies async database connectivity by executing a lightweight query.",
    status_code=status.HTTP_200_OK,
)
async def db_health_check(
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        result = await db.execute(text("SELECT 1"))
        scalar = result.scalar()
        if scalar == 1:
            return {"status": "ok", "database": "connected"}
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "error", "database": "unexpected response"},
        )
    except Exception as exc:
        logger.error(f"Database health check failed: {exc.__class__.__name__}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "error", "database": "disconnected"},
        )
