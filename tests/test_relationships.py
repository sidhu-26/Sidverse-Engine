from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Activity,
    ActivityAction,
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
)


@pytest.mark.asyncio
async def test_complete_entity_graph_integration(db_session: AsyncSession) -> None:
    """Integration test verifying realistic entity graph persistence and cascading.

    Graph:
    User -> Project -> Task -> Schedule -> Reminder -> Notification -> Activity
    """
    # 1. Create User
    user = User(
        email="antigravity_lead@example.com",
        display_name="Sid Lead",
        timezone="Asia/Kolkata",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # 2. Create Project
    project = Project(
        user_id=user.id,
        name="SID//OS v1.0",
        description="Autonomous Personal Operating System",
        status=ProjectStatus.ACTIVE,
        priority=ProjectPriority.HIGH,
        target_date=datetime(2026, 12, 31, 23, 59, tzinfo=UTC),
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    # 3. Create Task linked to Project
    task = Task(
        user_id=user.id,
        project_id=project.id,
        title="Complete Phase 1 Database",
        description="Write models and migrations",
        status=TaskStatus.TODO,
        priority=TaskPriority.URGENT,
        due_at=datetime(2026, 10, 8, 20, 0, tzinfo=UTC),
        estimated_minutes=90,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    # 4. Create Schedule linked to Task
    schedule_start = datetime(2026, 10, 8, 18, 0, tzinfo=UTC)
    schedule_end = datetime(2026, 10, 8, 19, 30, tzinfo=UTC)
    schedule = Schedule(
        user_id=user.id,
        task_id=task.id,
        title="Coding Phase 1",
        start_at=schedule_start,
        end_at=schedule_end,
        status=ScheduleStatus.IN_PROGRESS,
    )
    db_session.add(schedule)
    await db_session.commit()
    await db_session.refresh(schedule)

    # 5. Create Reminder for Task & Schedule
    reminder = Reminder(
        user_id=user.id,
        task_id=task.id,
        schedule_id=schedule.id,
        remind_at=schedule_start,
        status=ReminderStatus.PENDING,
    )
    db_session.add(reminder)
    await db_session.commit()
    await db_session.refresh(reminder)

    # 6. Create Notification
    notification = Notification(
        user_id=user.id,
        type=NotificationType.REMINDER,
        title="Session starting",
        message="Coding Phase 1 starts now.",
        scheduled_for=schedule_start,
    )
    db_session.add(notification)
    await db_session.commit()
    await db_session.refresh(notification)

    # 7. Create Activity
    activity = Activity(
        user_id=user.id,
        entity_type="TASK",
        entity_id=task.id,
        action=ActivityAction.TASK_CREATED,
        metadata_={"project_name": project.name, "priority": task.priority.value},
    )
    db_session.add(activity)
    await db_session.commit()
    await db_session.refresh(activity)

    # 8. Query and verify graph integrity
    stmt_task = select(Task).where(Task.id == task.id)
    res_task = await db_session.execute(stmt_task)
    fetched_task = res_task.scalar_one()

    assert fetched_task.project_id == project.id
    assert fetched_task.user_id == user.id

    stmt_rem = select(Reminder).where(Reminder.id == reminder.id)
    res_rem = await db_session.execute(stmt_rem)
    fetched_rem = res_rem.scalar_one()

    assert fetched_rem.task_id == task.id
    assert fetched_rem.schedule_id == schedule.id


@pytest.mark.asyncio
async def test_project_deletion_sets_task_project_id_null(db_session: AsyncSession) -> None:
    """Deleting a project should SET NULL on task.project_id rather than deleting tasks."""
    user = User(email="test_cascade@example.com", display_name="Test User")
    db_session.add(user)
    await db_session.commit()

    project = Project(user_id=user.id, name="Temp Project")
    db_session.add(project)
    await db_session.commit()

    task = Task(user_id=user.id, project_id=project.id, title="Independent Task")
    db_session.add(task)
    await db_session.commit()

    # Delete project
    await db_session.delete(project)
    await db_session.commit()

    # Verify task still exists but project_id is None
    stmt = select(Task).where(Task.id == task.id)
    res = await db_session.execute(stmt)
    remaining_task = res.scalar_one_or_none()

    assert remaining_task is not None
    assert remaining_task.project_id is None


@pytest.mark.asyncio
async def test_goal_milestones_and_duty_recurrence_cascade(db_session: AsyncSession) -> None:
    """Deleting a goal cascades to its milestones; deleting a duty cascades to recurrence."""
    user = User(email="cascade_test@example.com", display_name="Cascade User")
    db_session.add(user)
    await db_session.commit()

    goal = Goal(user_id=user.id, title="Goal with Milestones", status=GoalStatus.ACTIVE)
    db_session.add(goal)
    await db_session.commit()

    m1 = GoalMilestone(goal_id=goal.id, title="M1", position=0)
    db_session.add(m1)
    await db_session.commit()

    duty = Duty(user_id=user.id, title="Duty with Rule", priority=DutyPriority.LOW)
    db_session.add(duty)
    await db_session.commit()

    rule = RecurrenceRule(
        user_id=user.id,
        duty_id=duty.id,
        frequency=RecurrenceFrequency.DAILY,
    )
    db_session.add(rule)
    await db_session.commit()

    # Delete goal
    await db_session.delete(goal)
    # Delete duty
    await db_session.delete(duty)
    await db_session.commit()

    # Verify milestone is deleted
    stmt_m = select(GoalMilestone).where(GoalMilestone.id == m1.id)
    m_check = (await db_session.execute(stmt_m)).scalar_one_or_none()
    assert m_check is None

    # Verify recurrence rule is deleted
    stmt_r = select(RecurrenceRule).where(RecurrenceRule.id == rule.id)
    r_check = (await db_session.execute(stmt_r)).scalar_one_or_none()
    assert r_check is None
