from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.database import AsyncSessionLocal
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


@pytest.mark.asyncio
async def test_postgres_native_types_and_constraints() -> None:
    """Verify that PostgreSQL 17 handles UUID, TIMESTAMPTZ, JSONB, and constraints natively."""
    async with AsyncSessionLocal() as session:
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
