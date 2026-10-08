from fastapi import APIRouter

from app.api.health import router as health_router

api_router = APIRouter()

# Register Phase 0 routers
api_router.include_router(health_router)
