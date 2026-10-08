from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import NullPool, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import hash_password, hash_session_token, verify_password
from app.models import (
    Activity,
    ActivityAction,
    DailyReview,
    Goal,
    GoalStatus,
    Project,
    ProjectPriority,
    ProjectStatus,
    Task,
    TaskPriority,
    TaskStatus,
    User,
    UserSession,
)


def get_live_postgres_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Create a sessionmaker with NullPool for isolated async event loops."""
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


@pytest.mark.asyncio
async def test_postgres_native_types_and_constraints() -> None:
    """Verify that PostgreSQL 17 handles UUID, TIMESTAMPTZ, JSONB, and constraints natively."""
    sessionmaker = get_live_postgres_sessionmaker()
    async with sessionmaker() as session:
        # 1. Clean up any leftover test data
        await session.execute(text("DELETE FROM users WHERE email LIKE 'pg_test_%'"))
        await session.commit()

        # 2. Test User with UUID, Timezone, and Argon2id hash
        hashed_pw = hash_password("PostgresPassword123")
        user = User(
            email="pg_test_user@example.com",
            display_name="PG Test User",
            password_hash=hashed_pw,
            timezone="Asia/Kolkata",
        )
        session.add(user)
        await session.commit()
        user_id = user.id

        # Query user back to verify timezone and password verification
        stmt_u = select(User).where(User.id == user_id)
        user_res = (await session.execute(stmt_u)).scalar_one()
        assert user_res.created_at.tzinfo is not None
        assert verify_password("PostgresPassword123", user_res.password_hash)

        # 3. Test Session persistence in PostgreSQL 17
        token_hash = hash_session_token("pg_random_raw_session_token_123")
        user_session = UserSession(
            user_id=user_id,
            session_token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=7),
            user_agent="PostgresIntegrationTest/1.0",
            ip_address="127.0.0.1",
        )
        session.add(user_session)
        await session.commit()

        stmt_s = select(UserSession).where(UserSession.session_token_hash == token_hash)
        res_s = await session.execute(stmt_s)
        fetched_s = res_s.scalar_one()
        assert fetched_s.user_id == user_id
        assert fetched_s.is_revoked is False

        # 4. Test Goal Check Constraint (0 <= progress <= 100)
        goal_valid = Goal(
            user_id=user_id,
            title="Valid Goal",
            progress=50,
            status=GoalStatus.ACTIVE,
        )
        session.add(goal_valid)
        await session.commit()
        valid_goal_id = goal_valid.id

        goal_invalid = Goal(
            user_id=user_id,
            title="Invalid Goal",
            progress=150,
            status=GoalStatus.ACTIVE,
        )
        session.add(goal_invalid)
        with pytest.raises((IntegrityError, DBAPIError)):
            await session.commit()
        await session.rollback()

        # 5. Test Activity with native JSONB column
        activity = Activity(
            user_id=user_id,
            entity_type="GOAL",
            entity_id=valid_goal_id,
            action=ActivityAction.GOAL_UPDATED,
            metadata_={
                "changes": {"progress": {"old": 0, "new": 50}},
                "nested_array": [1, 2, 3],
                "boolean_flag": True,
            },
        )
        session.add(activity)
        await session.commit()

        # Query JSONB back
        stmt_a = select(Activity).where(Activity.id == activity.id)
        res_a = await session.execute(stmt_a)
        fetched_act = res_a.scalar_one()
        assert fetched_act.metadata_["changes"]["progress"]["new"] == 50
        assert fetched_act.metadata_["boolean_flag"] is True

        # 6. Test Project -> Task Set Null on Project Delete
        project = Project(
            user_id=user_id,
            name="PG Project",
            status=ProjectStatus.ACTIVE,
            priority=ProjectPriority.HIGH,
        )
        session.add(project)
        await session.commit()
        project_id = project.id

        task = Task(
            user_id=user_id,
            project_id=project_id,
            title="PG Task",
            status=TaskStatus.TODO,
            priority=TaskPriority.MEDIUM,
            due_at=datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC),
        )
        session.add(task)
        await session.commit()
        task_id = task.id

        assert task.project_id == project_id

        # Delete project -> task.project_id should SET NULL in PostgreSQL
        stmt_p = select(Project).where(Project.id == project_id)
        p_to_del = (await session.execute(stmt_p)).scalar_one()
        await session.delete(p_to_del)
        await session.commit()

        stmt_t = select(Task).where(Task.id == task_id)
        res_t = await session.execute(stmt_t)
        t_after = res_t.scalar_one()
        assert t_after.project_id is None

        # 7. Test Daily Review Unique Constraint
        daily = DailyReview(
            user_id=user_id,
            review_date=date(2026, 10, 8),
            completed_tasks=3,
        )
        session.add(daily)
        await session.commit()

        duplicate_daily = DailyReview(
            user_id=user_id,
            review_date=date(2026, 10, 8),
            completed_tasks=1,
        )
        session.add(duplicate_daily)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

        # 8. Clean up test user (will CASCADE delete sessions, activities, tasks, goals)
        del_stmt = select(User).where(User.id == user_id)
        u_to_delete = (await session.execute(del_stmt)).scalar_one_or_none()
        if u_to_delete:
            await session.delete(u_to_delete)
            await session.commit()


@pytest.mark.asyncio
async def test_postgres_live_task_engine() -> None:
    """Verify Task Engine service and repository logic on live PostgreSQL 17."""
    from app.schemas.task import TaskCreate, TaskUpdate
    from app.services.task_service import TaskService

    sessionmaker = get_live_postgres_sessionmaker()
    async with sessionmaker() as session:
        # Create user
        user = User(
            email="pg_test_tasks_user@example.com",
            display_name="PG Task User",
            password_hash=hash_password("Pass123!"),
            timezone="UTC",
        )
        session.add(user)
        await session.commit()
        user_id = user.id

        service = TaskService(session)

        # 1. Create Task
        created = await service.create_task(
            user_id=user_id,
            data=TaskCreate(
                title="PostgreSQL Native Task",
                description="Testing native PG operations",
                priority=TaskPriority.HIGH,
                due_at=datetime.now(UTC) + timedelta(days=1),
                estimated_minutes=30,
            ),
        )
        assert created.title == "PostgreSQL Native Task"
        assert created.status == TaskStatus.TODO

        # 2. Update to COMPLETED
        completed = await service.update_task(
            task_id=created.id,
            user_id=user_id,
            data=TaskUpdate(status=TaskStatus.COMPLETED),
        )
        assert completed.status == TaskStatus.COMPLETED
        assert completed.completed_at is not None

        # 3. Soft Delete
        await service.delete_task(task_id=created.id, user_id=user_id)

        # Verify activity was recorded in native JSONB activities table
        stmt_act = select(Activity).where(
            Activity.user_id == user_id, Activity.entity_id == created.id
        )
        acts = list((await session.execute(stmt_act)).scalars().all())
        assert len(acts) == 3  # CREATED, COMPLETED, DELETED

        # Clean up
        del_u = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
        await session.delete(del_u)
        await session.commit()


@pytest.mark.asyncio
async def test_postgres_live_phases_4_5_6() -> None:
    """Verify Schedules, Reminders, Notifications, Projects, and Goals on live PostgreSQL 17."""
    from app.schemas.goal import GoalCreate, GoalMilestoneCreate, GoalMilestoneUpdate
    from app.schemas.project import ProjectCreate
    from app.schemas.reminder import ReminderCreate
    from app.schemas.schedule import ScheduleCreate
    from app.services.goal_service import GoalService
    from app.services.notification_service import NotificationService
    from app.services.project_service import ProjectService
    from app.services.reminder_service import ReminderService
    from app.services.schedule_service import ScheduleService

    sessionmaker = get_live_postgres_sessionmaker()
    async with sessionmaker() as session:
        # 1. Create User
        user = User(
            email="pg_test_full_user@example.com",
            display_name="PG Full Phases User",
            password_hash=hash_password("Pass123!"),
            timezone="UTC",
        )
        session.add(user)
        await session.commit()
        user_id = user.id

        # 2. Project
        p_svc = ProjectService(session)
        project = await p_svc.create_project(
            user_id=user_id,
            data=ProjectCreate(name="Live PG Project", priority=ProjectPriority.HIGH),
        )
        assert project.name == "Live PG Project"

        # 3. Schedule
        s_svc = ScheduleService(session)
        start = datetime.now(UTC) + timedelta(hours=2)
        end = start + timedelta(hours=1)
        schedule = await s_svc.create_schedule(
            user_id=user_id,
            data=ScheduleCreate(
                title="Live PG Schedule",
                start_at=start,
                end_at=end,
            ),
        )
        assert schedule.title == "Live PG Schedule"

        # 4. Reminder & Notification
        r_svc = ReminderService(session)
        remind_at = datetime.now(UTC) + timedelta(hours=1)
        reminder = await r_svc.create_reminder(
            user_id=user_id,
            data=ReminderCreate(
                schedule_id=schedule.id,
                remind_at=remind_at,
            ),
        )
        assert reminder.schedule_id == schedule.id

        # Trigger reminder
        await r_svc.trigger_reminder(reminder.id)

        # Check notification
        n_svc = NotificationService(session)
        notifs = await n_svc.list_notifications(user_id=user_id)
        assert notifs.total == 1
        assert "Live PG Schedule" in notifs.items[0].title

        # 5. Goal & Milestone
        g_svc = GoalService(session)
        goal = await g_svc.create_goal(
            user_id=user_id,
            data=GoalCreate(title="Live PG Goal", progress=25),
        )
        assert goal.progress == 25

        milestone = await g_svc.create_milestone(
            goal_id=goal.id,
            user_id=user_id,
            data=GoalMilestoneCreate(title="Live Milestone 1", position=1),
        )
        assert milestone.title == "Live Milestone 1"

        milestone_done = await g_svc.update_milestone(
            goal_id=goal.id,
            milestone_id=milestone.id,
            user_id=user_id,
            data=GoalMilestoneUpdate(is_completed=True),
        )
        assert milestone_done.is_completed is True
        assert milestone_done.completed_at is not None

        # Clean up user (cascades all owned items)
        del_u = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
        await session.delete(del_u)
        await session.commit()
