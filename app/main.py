import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import logger, setup_logging
from app.core.scheduler import app_scheduler

settings = get_settings()
setup_logging(log_level=settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan context manager."""
    logger.info(f"Starting {settings.APP_NAME} in [{settings.APP_ENV}] mode...")
    app_scheduler.start()
    try:
        from app.services.reminder_service import ReminderService

        rebuilt = await ReminderService.rebuild_all_pending_reminders()
        logger.info(f"Rebuilt {rebuilt} pending reminder scheduler jobs from PostgreSQL.")
    except Exception as e:
        logger.warning(f"Could not rebuild scheduler jobs on startup: {e}")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}...")
    app_scheduler.shutdown(wait=False)


def create_application() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title=settings.APP_NAME,
        description="Private personal assistant backend.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # 1. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Security Headers Middleware
    class SecurityHeadersMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
            response = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["X-Frame-Options"] = "DENY"
            return response

    app.add_middleware(SecurityHeadersMiddleware)

    # 3. Request Logging Middleware
    class RequestLoggingMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
            start_time = time.perf_counter()
            response = await call_next(request)
            process_time_ms = (time.perf_counter() - start_time) * 1000.0

            # Format: GET /api/health -> 200 -> 1.25ms
            logger.info(
                "%s %s -> %s -> %.2fms",
                request.method,
                request.url.path,
                response.status_code,
                process_time_ms,
            )
            return response

    app.add_middleware(RequestLoggingMiddleware)

    # 4. Register Exception Handlers
    register_exception_handlers(app)

    # 5. Include API Router
    app.include_router(api_router, prefix=settings.API_PREFIX)

    return app


app = create_application()
