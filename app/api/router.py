from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.goals import router as goals_router
from app.api.health import router as health_router
from app.api.notifications import router as notifications_router
from app.api.projects import router as projects_router
from app.api.reminders import router as reminders_router
from app.api.schedules import router as schedules_router
from app.api.tasks import router as tasks_router

api_router = APIRouter()

# Register API routers
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(tasks_router)
api_router.include_router(schedules_router)
api_router.include_router(reminders_router)
api_router.include_router(notifications_router)
api_router.include_router(projects_router)
api_router.include_router(goals_router)
