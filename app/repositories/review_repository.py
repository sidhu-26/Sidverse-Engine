import uuid
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TaskStatus
from app.models.review import DailyReview, WeeklyReview
from app.models.task import Task


class ReviewRepository:
    """Repository for Daily and Weekly Review entity operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # =========================================================================
    # Daily Reviews
    # =========================================================================

    async def get_daily_review(
        self,
        user_id: uuid.UUID,
        review_date: date,
    ) -> DailyReview | None:
        """Fetch daily review for a specific user and date."""
        stmt = select(DailyReview).where(
            DailyReview.user_id == user_id,
            DailyReview.review_date == review_date,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_daily_review_by_id(
        self,
        user_id: uuid.UUID,
        review_id: uuid.UUID,
    ) -> DailyReview | None:
        """Fetch daily review by its primary key ID."""
        stmt = select(DailyReview).where(
            DailyReview.id == review_id,
            DailyReview.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_daily_review(self, review: DailyReview) -> DailyReview:
        """Persist a new daily review."""
        self.session.add(review)
        await self.session.commit()
        await self.session.refresh(review)
        return review

    async def update_daily_review(self, review: DailyReview) -> DailyReview:
        """Commit changes to an existing daily review."""
        await self.session.commit()
        await self.session.refresh(review)
        return review

    async def list_daily_reviews(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[DailyReview], int]:
        """List daily reviews for user ordered by review_date desc."""
        query = select(DailyReview).where(DailyReview.user_id == user_id)

        count_stmt = select(func.count()).select_from(query.subquery())
        total_count = (await self.session.execute(count_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(DailyReview.review_date.desc()).offset(offset).limit(page_size)

        result = await self.session.execute(query)
        items = list(result.scalars().all())
        return items, total_count

    # =========================================================================
    # Weekly Reviews
    # =========================================================================

    async def get_weekly_review(
        self,
        user_id: uuid.UUID,
        week_start: date,
    ) -> WeeklyReview | None:
        """Fetch weekly review for a specific user and week start."""
        stmt = select(WeeklyReview).where(
            WeeklyReview.user_id == user_id,
            WeeklyReview.week_start == week_start,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_weekly_review_by_id(
        self,
        user_id: uuid.UUID,
        review_id: uuid.UUID,
    ) -> WeeklyReview | None:
        """Fetch weekly review by ID."""
        stmt = select(WeeklyReview).where(
            WeeklyReview.id == review_id,
            WeeklyReview.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_weekly_review(self, review: WeeklyReview) -> WeeklyReview:
        """Persist a new weekly review."""
        self.session.add(review)
        await self.session.commit()
        await self.session.refresh(review)
        return review

    async def update_weekly_review(self, review: WeeklyReview) -> WeeklyReview:
        """Commit changes to an existing weekly review."""
        await self.session.commit()
        await self.session.refresh(review)
        return review

    async def list_weekly_reviews(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[WeeklyReview], int]:
        """List weekly reviews for user ordered by week_start desc."""
        query = select(WeeklyReview).where(WeeklyReview.user_id == user_id)

        count_stmt = select(func.count()).select_from(query.subquery())
        total_count = (await self.session.execute(count_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(WeeklyReview.week_start.desc()).offset(offset).limit(page_size)

        result = await self.session.execute(query)
        items = list(result.scalars().all())
        return items, total_count

    # =========================================================================
    # Metric Calculations
    # =========================================================================

    async def count_completed_tasks_in_range(
        self,
        user_id: uuid.UUID,
        start_utc: datetime,
        end_utc: datetime,
    ) -> int:
        """Count tasks completed within [start_utc, end_utc)."""
        stmt = select(func.count(Task.id)).where(
            Task.user_id == user_id,
            Task.deleted_at.is_(None),
            Task.status == TaskStatus.COMPLETED,
            Task.completed_at >= start_utc,
            Task.completed_at < end_utc,
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def count_incomplete_tasks_in_range(
        self,
        user_id: uuid.UUID,
        start_utc: datetime,
        end_utc: datetime,
    ) -> int:
        """Count incomplete tasks relevant to the period (due in period or created prior)."""
        stmt = select(func.count(Task.id)).where(
            Task.user_id == user_id,
            Task.deleted_at.is_(None),
            Task.status.not_in([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
            (
                (Task.due_at >= start_utc) & (Task.due_at < end_utc)
                | (Task.due_at.is_(None) & (Task.created_at < end_utc))
            ),
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def count_overdue_tasks_as_of(
        self,
        user_id: uuid.UUID,
        as_of_utc: datetime,
    ) -> int:
        """Count tasks overdue as of a given timestamp."""
        stmt = select(func.count(Task.id)).where(
            Task.user_id == user_id,
            Task.deleted_at.is_(None),
            Task.status.not_in([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
            Task.due_at.is_not(None),
            Task.due_at < as_of_utc,
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0
