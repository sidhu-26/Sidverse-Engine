from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Activity,
    ActivityAction,
    DailyReview,
    Duty,
    DutyPriority,
    Goal,
    GoalMilestone,
    GoalStatus,
    Notification,
    NotificationType,
    Project,
    ProjectPriority,
    ProjectStatus,
    RecurrenceFrequency,
    RecurrenceRule,
    Reminder,
    ReminderStatus,
    Schedule,
    ScheduleStatus,
    Task,
    TaskPriority,
    TaskStatus,
    User,
    WeeklyReview,
)


@pytest.mark.asyncio
async def test_user_creation_and_email_uniqueness(db_session: AsyncSession) -> None:
    """Test user model creation and unique email constraint."""
    user1 = User(
        email="sid@example.com",
        display_name="Sid",
        timezone="Asia/Kolkata",
    )
    db_session.add(user1)
    await db_session.commit()
    await db_session.refresh(user1)

    assert user1.id is not None
    assert user1.is_active is True
    assert user1.created_at is not None
    assert user1.updated_at is not None

    # Duplicate email must fail
    user2 = User(
        email="sid@example.com",
        display_name="Duplicate Sid",
    )
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_project_and_task_relationships(db_session: AsyncSession) -> None:
    """Test project and task models, foreign keys, and soft delete fields."""
    user = User(email="project_user@example.com", display_name="Dev User")
    db_session.add(user)
    await db_session.commit()

    project = Project(
        user_id=user.id,
        name="SID//OS Backend",
        description="FastAPI + PostgreSQL architecture",
        status=ProjectStatus.ACTIVE,
        priority=ProjectPriority.HIGH,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    task = Task(
        user_id=user.id,
        project_id=project.id,
        title="Setup database models",
        description="Phase 1 architecture",
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
        estimated_minutes=60,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    assert task.project_id == project.id
    assert task.status == TaskStatus.IN_PROGRESS
    assert task.priority == TaskPriority.HIGH
    assert task.deleted_at is None


@pytest.mark.asyncio
async def test_goal_and_milestones(db_session: AsyncSession) -> None:
    """Test goal and ordered milestones."""
    user = User(email="goal_user@example.com", display_name="Goal Achiever")
    db_session.add(user)
    await db_session.commit()

    goal = Goal(
        user_id=user.id,
        title="Launch Personal Assistant",
        status=GoalStatus.ACTIVE,
        progress=25,
    )
    db_session.add(goal)
    await db_session.commit()

    m1 = GoalMilestone(goal_id=goal.id, title="Phase 0 Foundation", position=0, is_completed=True)
    m2 = GoalMilestone(goal_id=goal.id, title="Phase 1 Database", position=1, is_completed=False)
    db_session.add_all([m1, m2])
    await db_session.commit()

    stmt = select(Goal).where(Goal.id == goal.id)
    result = await db_session.execute(stmt)
    fetched_goal = result.scalar_one()

    # Load relationship
    stmt_m = (
        select(GoalMilestone)
        .where(GoalMilestone.goal_id == goal.id)
        .order_by(GoalMilestone.position)
    )
    res_m = await db_session.execute(stmt_m)
    milestones = res_m.scalars().all()

    assert fetched_goal.progress == 25
    assert len(milestones) == 2
    assert milestones[0].title == "Phase 0 Foundation"
    assert milestones[0].is_completed is True
    assert milestones[1].position == 1


@pytest.mark.asyncio
async def test_duty_and_recurrence_rule(db_session: AsyncSession) -> None:
    """Test duty with associated 1-to-1 recurrence rule."""
    user = User(email="duty_user@example.com", display_name="Duty Master")
    db_session.add(user)
    await db_session.commit()

    duty = Duty(
        user_id=user.id,
        title="Review Weekly Priorities",
        priority=DutyPriority.HIGH,
    )
    db_session.add(duty)
    await db_session.commit()

    rule = RecurrenceRule(
        user_id=user.id,
        duty_id=duty.id,
        frequency=RecurrenceFrequency.WEEKLY,
        interval=1,
        by_weekday="SUN",
    )
    db_session.add(rule)
    await db_session.commit()

    stmt = select(RecurrenceRule).where(RecurrenceRule.duty_id == duty.id)
    result = await db_session.execute(stmt)
    fetched_rule = result.scalar_one()

    assert fetched_rule.frequency == RecurrenceFrequency.WEEKLY
    assert fetched_rule.by_weekday == "SUN"


@pytest.mark.asyncio
async def test_schedule_and_reminders(db_session: AsyncSession) -> None:
    """Test planned schedules and reminder triggers."""
    user = User(email="sched_user@example.com", display_name="Scheduler")
    db_session.add(user)
    await db_session.commit()

    start_time = datetime(2026, 10, 9, 10, 0, tzinfo=UTC)
    end_time = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)

    schedule = Schedule(
        user_id=user.id,
        title="Deep Work Session",
        start_at=start_time,
        end_at=end_time,
        status=ScheduleStatus.SCHEDULED,
    )
    db_session.add(schedule)
    await db_session.commit()

    reminder = Reminder(
        user_id=user.id,
        schedule_id=schedule.id,
        remind_at=start_time,
        status=ReminderStatus.PENDING,
    )
    db_session.add(reminder)
    await db_session.commit()

    assert reminder.id is not None
    assert reminder.status == ReminderStatus.PENDING


@pytest.mark.asyncio
async def test_activity_jsonb_metadata(db_session: AsyncSession) -> None:
    """Test activity stream logging with JSON structured metadata."""
    user = User(email="activity_user@example.com", display_name="Auditor")
    db_session.add(user)
    await db_session.commit()

    activity = Activity(
        user_id=user.id,
        entity_type="TASK",
        action=ActivityAction.TASK_COMPLETED,
        metadata_={"estimated_minutes": 45, "actual_minutes": 35},
    )
    db_session.add(activity)
    await db_session.commit()
    await db_session.refresh(activity)

    assert activity.metadata_ == {"estimated_minutes": 45, "actual_minutes": 35}
    assert activity.action == ActivityAction.TASK_COMPLETED


@pytest.mark.asyncio
async def test_notification_model(db_session: AsyncSession) -> None:
    """Test user notification creation and delivery states."""
    user = User(email="notif_user@example.com", display_name="Recipient")
    db_session.add(user)
    await db_session.commit()

    notification = Notification(
        user_id=user.id,
        type=NotificationType.REMINDER,
        title="Meeting in 15 minutes",
        message="Daily sync with engineering",
    )
    db_session.add(notification)
    await db_session.commit()

    assert notification.id is not None
    assert notification.read_at is None


@pytest.mark.asyncio
async def test_reviews_uniqueness_constraints(db_session: AsyncSession) -> None:
    """Test uniqueness constraints on daily reviews (user_id + review_date) and weekly reviews."""
    user = User(email="review_user@example.com", display_name="Reviewer")
    db_session.add(user)
    await db_session.commit()
    user_id = user.id

    today = date(2026, 10, 8)
    daily = DailyReview(
        user_id=user_id,
        review_date=today,
        completed_tasks=5,
        incomplete_tasks=1,
    )
    db_session.add(daily)
    await db_session.commit()

    # Second daily review for same user & date must fail
    duplicate_daily = DailyReview(
        user_id=user_id,
        review_date=today,
        completed_tasks=2,
    )
    db_session.add(duplicate_daily)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    # Weekly review
    week_start = date(2026, 10, 5)
    week_end = date(2026, 10, 11)
    weekly = WeeklyReview(
        user_id=user_id,
        week_start=week_start,
        week_end=week_end,
        completed_tasks=20,
    )
    db_session.add(weekly)
    await db_session.commit()

    # Duplicate weekly review for same user & week_start must fail
    duplicate_weekly = WeeklyReview(
        user_id=user_id,
        week_start=week_start,
        week_end=week_end,
    )
    db_session.add(duplicate_weekly)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
