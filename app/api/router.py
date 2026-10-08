from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.tasks import router as tasks_router

api_router = APIRouter()

# Register Phase 0, Phase 2 & Phase 3 routers
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(tasks_router)
