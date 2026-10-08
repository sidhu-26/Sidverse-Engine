import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger("sid_os.scheduler")


class AppScheduler:
    """Core APScheduler wrapper managing background timing and deterministic jobs."""

    def __init__(self) -> None:
        self._scheduler: AsyncIOScheduler | None = None

    @property
    def scheduler(self) -> AsyncIOScheduler:
        if self._scheduler is None:
            self._scheduler = AsyncIOScheduler()
        return self._scheduler

    @property
    def is_running(self) -> bool:
        return self._scheduler is not None and self._scheduler.running

    def start(self) -> None:
        """Start the background AsyncIOScheduler if not already running."""
        if not self.is_running:
            try:
                self.scheduler.start()
                logger.info("APScheduler started successfully.")
            except Exception as e:
                logger.error(f"Failed to start APScheduler: {e}")

    def shutdown(self, wait: bool = False) -> None:
        """Gracefully stop the background AsyncIOScheduler."""
        if self.is_running and self._scheduler is not None:
            try:
                self._scheduler.shutdown(wait=wait)
                logger.info("APScheduler stopped gracefully.")
            except Exception as e:
                logger.error(f"Error shutting down APScheduler: {e}")

    def add_date_job(
        self,
        job_id: str,
        func: Callable[..., Any],
        run_date: datetime,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> bool:
        """Register or replace a one-time job at run_date with a deterministic job_id."""
        try:
            self.remove_job(job_id)
            self.scheduler.add_job(
                func,
                trigger="date",
                run_date=run_date,
                id=job_id,
                args=args or [],
                kwargs=kwargs or {},
                replace_existing=True,
            )
            logger.info(f"Registered scheduled job '{job_id}' at {run_date.isoformat()}")
            return True
        except Exception as e:
            logger.error(f"Failed to add job '{job_id}': {e}")
            return False

    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job if it exists."""
        try:
            if self._scheduler:
                removed = False
                while self._scheduler.get_job(job_id):
                    self._scheduler.remove_job(job_id)
                    removed = True
                if removed:
                    logger.info(f"Removed scheduled job '{job_id}'")
                    return True
        except Exception as e:
            logger.warning(f"Failed to remove job '{job_id}': {e}")
        return False

    def get_job(self, job_id: str) -> Any:
        """Retrieve scheduled job instance by ID."""
        if self._scheduler:
            return self._scheduler.get_job(job_id)
        return None

    def get_jobs(self) -> list[Any]:
        """Return list of all registered jobs."""
        if self._scheduler:
            return self._scheduler.get_jobs()
        return []


# Global singleton scheduler instance
app_scheduler = AppScheduler()
