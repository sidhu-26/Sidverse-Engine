from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
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
from app.services.review_service import ReviewService

router = APIRouter(prefix="/reviews", tags=["Reviews"])


# =============================================================================
# Daily Review Endpoints
# =============================================================================


@router.post(
    "/daily",
    response_model=DailyReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Create or Upsert Daily Review",
    description=(
        "Calculate metrics and persist/upsert daily review for specified date "
        "(defaults to today in user timezone)."
    ),
)
async def create_or_upsert_daily_review(
    body: DailyReviewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DailyReviewResponse:
    review_service = ReviewService(db)
    return await review_service.create_or_upsert_daily_review(user=current_user, payload=body)


@router.get(
    "/daily",
    response_model=DailyReviewListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Daily Reviews",
    description="Retrieve paginated list of past daily reviews for the current user.",
)
async def list_daily_reviews(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DailyReviewListResponse:
    review_service = ReviewService(db)
    return await review_service.list_daily_reviews(
        user=current_user, page=page, page_size=page_size
    )


@router.get(
    "/daily/{review_date}",
    response_model=DailyReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Daily Review Detail",
    description="Retrieve daily review for a specific calendar date (YYYY-MM-DD).",
)
async def get_daily_review(
    review_date: date,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DailyReviewResponse:
    review_service = ReviewService(db)
    return await review_service.get_daily_review(user=current_user, review_date=review_date)


@router.patch(
    "/daily/{review_date}",
    response_model=DailyReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Daily Review",
    description="Update user notes or recalculate task metrics for a specific daily review.",
)
async def update_daily_review(
    review_date: date,
    body: DailyReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DailyReviewResponse:
    review_service = ReviewService(db)
    return await review_service.update_daily_review(
        user=current_user,
        review_date=review_date,
        payload=body,
    )


# =============================================================================
# Weekly Review Endpoints
# =============================================================================


@router.post(
    "/weekly",
    response_model=WeeklyReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Create or Upsert Weekly Review",
    description=(
        "Calculate metrics and persist/upsert weekly review for specified week start "
        "(normalized to Monday)."
    ),
)
async def create_or_upsert_weekly_review(
    body: WeeklyReviewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WeeklyReviewResponse:
    review_service = ReviewService(db)
    return await review_service.create_or_upsert_weekly_review(user=current_user, payload=body)


@router.get(
    "/weekly",
    response_model=WeeklyReviewListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Weekly Reviews",
    description="Retrieve paginated list of past weekly reviews for current user.",
)
async def list_weekly_reviews(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WeeklyReviewListResponse:
    review_service = ReviewService(db)
    return await review_service.list_weekly_reviews(
        user=current_user, page=page, page_size=page_size
    )


@router.get(
    "/weekly/{week_start}",
    response_model=WeeklyReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Weekly Review Detail",
    description=(
        "Retrieve weekly review for week starting on date (YYYY-MM-DD, normalized to Monday)."
    ),
)
async def get_weekly_review(
    week_start: date,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WeeklyReviewResponse:
    review_service = ReviewService(db)
    return await review_service.get_weekly_review(user=current_user, week_start=week_start)


@router.patch(
    "/weekly/{week_start}",
    response_model=WeeklyReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Weekly Review",
    description="Update user notes or recalculate task metrics for a specific weekly review.",
)
async def update_weekly_review(
    week_start: date,
    body: WeeklyReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WeeklyReviewResponse:
    review_service = ReviewService(db)
    return await review_service.update_weekly_review(
        user=current_user,
        week_start=week_start,
        payload=body,
    )
