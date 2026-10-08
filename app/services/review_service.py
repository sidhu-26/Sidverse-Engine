import math
import zoneinfo
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.enums import ActivityAction
from app.models.review import DailyReview, WeeklyReview
from app.models.user import User
from app.repositories.activity_repository import ActivityRepository
from app.repositories.review_repository import ReviewRepository
from app.schemas.review import (
    DailyReviewCreate,
    DailyReviewListResponse,
    DailyReviewResponse,
    DailyReviewUpdate,
    WeeklyReviewCreate,
    WeeklyReviewListResponse,
    WeeklyReviewResponse,
    WeeklyReviewUpdate,
)


class ReviewService:
    """Service for calculating and managing Daily and Weekly Reviews."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.review_repo = ReviewRepository(db)
        self.activity_repo = ActivityRepository(db)

    def _get_user_tz(self, user: User) -> zoneinfo.ZoneInfo:
        """Resolve user's timezone safely, defaulting to Asia/Kolkata if invalid/missing."""
        tz_name = user.timezone or "Asia/Kolkata"
        try:
            return zoneinfo.ZoneInfo(tz_name)
        except Exception:
            return zoneinfo.ZoneInfo("Asia/Kolkata")

    def _get_user_current_date(self, user: User) -> date:
        """Get the current calendar date in user's timezone."""
        tz = self._get_user_tz(user)
        return datetime.now(tz).date()

    def _get_daily_utc_range(self, user: User, review_date: date) -> tuple[datetime, datetime]:
        """Convert a local calendar date into [start_utc, end_utc) for user timezone."""
        tz = self._get_user_tz(user)
        start_local = datetime(
            review_date.year, review_date.month, review_date.day, 0, 0, 0, tzinfo=tz
        )
        end_local = start_local + timedelta(days=1)
        return start_local.astimezone(UTC), end_local.astimezone(UTC)

    def _get_weekly_utc_range(self, user: User, monday: date) -> tuple[datetime, datetime]:
        """Convert Monday date into [start_utc, end_utc) for the 7-day Monday-Sunday week."""
        tz = self._get_user_tz(user)
        start_local = datetime(monday.year, monday.month, monday.day, 0, 0, 0, tzinfo=tz)
        end_local = start_local + timedelta(days=7)
        return start_local.astimezone(UTC), end_local.astimezone(UTC)

    # =========================================================================
    # Daily Review Operations
    # =========================================================================

    async def calculate_daily_metrics(
        self,
        user: User,
        review_date: date,
    ) -> tuple[int, int, int, int]:
        """Compute (completed, incomplete, overdue, postponed) metrics for a single date."""
        start_utc, end_utc = self._get_daily_utc_range(user, review_date)

        completed = await self.review_repo.count_completed_tasks_in_range(
            user.id, start_utc, end_utc
        )
        incomplete = await self.review_repo.count_incomplete_tasks_in_range(
            user.id, start_utc, end_utc
        )
        overdue = await self.review_repo.count_overdue_tasks_as_of(user.id, end_utc)
        postponed = await self.activity_repo.count_actions_in_range(
            user.id,
            ActivityAction.TASK_RESCHEDULED,
            start_utc,
            end_utc,
        )
        return completed, incomplete, overdue, postponed

    async def create_or_upsert_daily_review(
        self,
        user: User,
        payload: DailyReviewCreate,
    ) -> DailyReviewResponse:
        """Create or upsert a daily review with fresh metrics from DB."""
        review_date = payload.review_date or self._get_user_current_date(user)
        completed, incomplete, overdue, postponed = await self.calculate_daily_metrics(
            user, review_date
        )

        existing = await self.review_repo.get_daily_review(user.id, review_date)
        if existing:
            existing.completed_tasks = completed
            existing.incomplete_tasks = incomplete
            existing.overdue_tasks = overdue
            existing.postponed_tasks = postponed
            if payload.notes is not None:
                existing.notes = payload.notes
            updated = await self.review_repo.update_daily_review(existing)
            return self._to_daily_response(updated)

        new_review = DailyReview(
            user_id=user.id,
            review_date=review_date,
            completed_tasks=completed,
            incomplete_tasks=incomplete,
            overdue_tasks=overdue,
            postponed_tasks=postponed,
            notes=payload.notes,
        )
        created = await self.review_repo.create_daily_review(new_review)

        await self.activity_repo.log_activity(
            user_id=user.id,
            entity_type="DAILY_REVIEW",
            entity_id=created.id,
            action=ActivityAction.DAILY_REVIEW_CREATED,
            metadata={"review_date": review_date.isoformat()},
        )
        return self._to_daily_response(created)

    async def get_daily_review(
        self,
        user: User,
        review_date: date,
    ) -> DailyReviewResponse:
        """Retrieve daily review by date. Returns 404 if not yet recorded."""
        review = await self.review_repo.get_daily_review(user.id, review_date)
        if not review:
            raise AppException(
                message=f"Daily review for {review_date} not found.",
                code="REVIEW_NOT_FOUND",
                status_code=404,
            )
        return self._to_daily_response(review)

    async def update_daily_review(
        self,
        user: User,
        review_date: date,
        payload: DailyReviewUpdate,
    ) -> DailyReviewResponse:
        """Partially update notes and/or recalculate metrics for an existing daily review."""
        review = await self.review_repo.get_daily_review(user.id, review_date)
        if not review:
            raise AppException(
                message=f"Daily review for {review_date} not found.",
                code="REVIEW_NOT_FOUND",
                status_code=404,
            )

        if payload.notes is not None:
            review.notes = payload.notes

        if payload.recalculate:
            completed, incomplete, overdue, postponed = await self.calculate_daily_metrics(
                user, review_date
            )
            review.completed_tasks = completed
            review.incomplete_tasks = incomplete
            review.overdue_tasks = overdue
            review.postponed_tasks = postponed

        updated = await self.review_repo.update_daily_review(review)

        await self.activity_repo.log_activity(
            user_id=user.id,
            entity_type="DAILY_REVIEW",
            entity_id=updated.id,
            action=ActivityAction.DAILY_REVIEW_UPDATED,
            metadata={"review_date": review_date.isoformat(), "recalculated": payload.recalculate},
        )
        return self._to_daily_response(updated)

    async def list_daily_reviews(
        self,
        user: User,
        page: int = 1,
        page_size: int = 20,
    ) -> DailyReviewListResponse:
        """List daily reviews for user."""
        items, total = await self.review_repo.list_daily_reviews(
            user.id, page=page, page_size=page_size
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return DailyReviewListResponse(
            items=[self._to_daily_response(r) for r in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    # =========================================================================
    # Weekly Review Operations
    # =========================================================================

    async def calculate_weekly_metrics(
        self,
        user: User,
        monday: date,
    ) -> tuple[int, int, int, int]:
        """Compute metrics for the 7-day Monday-Sunday week."""
        start_utc, end_utc = self._get_weekly_utc_range(user, monday)

        completed = await self.review_repo.count_completed_tasks_in_range(
            user.id, start_utc, end_utc
        )
        incomplete = await self.review_repo.count_incomplete_tasks_in_range(
            user.id, start_utc, end_utc
        )
        overdue = await self.review_repo.count_overdue_tasks_as_of(user.id, end_utc)
        postponed = await self.activity_repo.count_actions_in_range(
            user.id,
            ActivityAction.TASK_RESCHEDULED,
            start_utc,
            end_utc,
        )
        return completed, incomplete, overdue, postponed

    async def create_or_upsert_weekly_review(
        self,
        user: User,
        payload: WeeklyReviewCreate,
    ) -> WeeklyReviewResponse:
        """Create or upsert a weekly review. Normalizes week_start to Monday."""
        given_date = payload.week_start or self._get_user_current_date(user)
        monday = given_date - timedelta(days=given_date.weekday())
        sunday = monday + timedelta(days=6)

        completed, incomplete, overdue, postponed = await self.calculate_weekly_metrics(
            user, monday
        )

        existing = await self.review_repo.get_weekly_review(user.id, monday)
        if existing:
            existing.completed_tasks = completed
            existing.incomplete_tasks = incomplete
            existing.overdue_tasks = overdue
            existing.postponed_tasks = postponed
            if payload.notes is not None:
                existing.notes = payload.notes
            updated = await self.review_repo.update_weekly_review(existing)
            return self._to_weekly_response(updated)

        new_review = WeeklyReview(
            user_id=user.id,
            week_start=monday,
            week_end=sunday,
            completed_tasks=completed,
            incomplete_tasks=incomplete,
            overdue_tasks=overdue,
            postponed_tasks=postponed,
            notes=payload.notes,
        )
        created = await self.review_repo.create_weekly_review(new_review)

        await self.activity_repo.log_activity(
            user_id=user.id,
            entity_type="WEEKLY_REVIEW",
            entity_id=created.id,
            action=ActivityAction.WEEKLY_REVIEW_CREATED,
            metadata={"week_start": monday.isoformat(), "week_end": sunday.isoformat()},
        )
        return self._to_weekly_response(created)

    async def get_weekly_review(
        self,
        user: User,
        week_start: date,
    ) -> WeeklyReviewResponse:
        """Retrieve weekly review by week_start date (normalized to Monday)."""
        monday = week_start - timedelta(days=week_start.weekday())
        review = await self.review_repo.get_weekly_review(user.id, monday)
        if not review:
            raise AppException(
                message=f"Weekly review for week starting {monday} not found.",
                code="REVIEW_NOT_FOUND",
                status_code=404,
            )
        return self._to_weekly_response(review)

    async def update_weekly_review(
        self,
        user: User,
        week_start: date,
        payload: WeeklyReviewUpdate,
    ) -> WeeklyReviewResponse:
        """Partially update notes and/or recalculate metrics for weekly review."""
        monday = week_start - timedelta(days=week_start.weekday())
        review = await self.review_repo.get_weekly_review(user.id, monday)
        if not review:
            raise AppException(
                message=f"Weekly review for week starting {monday} not found.",
                code="REVIEW_NOT_FOUND",
                status_code=404,
            )

        if payload.notes is not None:
            review.notes = payload.notes

        if payload.recalculate:
            completed, incomplete, overdue, postponed = await self.calculate_weekly_metrics(
                user, monday
            )
            review.completed_tasks = completed
            review.incomplete_tasks = incomplete
            review.overdue_tasks = overdue
            review.postponed_tasks = postponed

        updated = await self.review_repo.update_weekly_review(review)

        await self.activity_repo.log_activity(
            user_id=user.id,
            entity_type="WEEKLY_REVIEW",
            entity_id=updated.id,
            action=ActivityAction.WEEKLY_REVIEW_UPDATED,
            metadata={"week_start": monday.isoformat(), "recalculated": payload.recalculate},
        )
        return self._to_weekly_response(updated)

    async def list_weekly_reviews(
        self,
        user: User,
        page: int = 1,
        page_size: int = 20,
    ) -> WeeklyReviewListResponse:
        """List weekly reviews for user."""
        items, total = await self.review_repo.list_weekly_reviews(
            user.id, page=page, page_size=page_size
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return WeeklyReviewListResponse(
            items=[self._to_weekly_response(r) for r in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def _to_daily_response(self, review: DailyReview) -> DailyReviewResponse:
        return DailyReviewResponse(
            id=review.id,
            user_id=review.user_id,
            review_date=review.review_date,
            completed_tasks=review.completed_tasks,
            incomplete_tasks=review.incomplete_tasks,
            overdue_tasks=review.overdue_tasks,
            postponed_tasks=review.postponed_tasks,
            notes=review.notes,
            created_at=review.created_at,
            updated_at=review.updated_at,
        )

    def _to_weekly_response(self, review: WeeklyReview) -> WeeklyReviewResponse:
        return WeeklyReviewResponse(
            id=review.id,
            user_id=review.user_id,
            week_start=review.week_start,
            week_end=review.week_end,
            completed_tasks=review.completed_tasks,
            incomplete_tasks=review.incomplete_tasks,
            overdue_tasks=review.overdue_tasks,
            postponed_tasks=review.postponed_tasks,
            notes=review.notes,
            created_at=review.created_at,
            updated_at=review.updated_at,
        )
