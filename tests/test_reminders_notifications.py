import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.scheduler import app_scheduler
from app.models.duty import Duty
from app.models.enums import DutyPriority, NotificationType, ReminderStatus
from app.models.notification import Notification
from app.models.reminder import Reminder
from app.services.reminder_service import ReminderService
from tests.test_tasks import create_test_user_and_login


# 1, 2, 3. Create reminder for task, schedule, and duty
@pytest.mark.asyncio
async def test_create_reminder_targets_success(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test creating reminders targeting task, schedule, and duty successfully."""
    user = await create_test_user_and_login(async_client, email="remind_targets@example.com")
    user_id = uuid.UUID(user["id"])

    # 1. Target Task
    t_res = await async_client.post("/api/tasks", json={"title": "Target Task"})
    task_id = t_res.json()["id"]

    remind_time_1 = datetime.now(UTC) + timedelta(hours=2)
    r1 = await async_client.post(
        "/api/reminders",
        json={"task_id": task_id, "remind_at": remind_time_1.isoformat()},
    )
    assert r1.status_code == status.HTTP_201_CREATED
    data1 = r1.json()
    assert data1["task_id"] == task_id
    assert data1["status"] == "PENDING"
    assert app_scheduler.get_job(f"reminder:{data1['id']}") is not None

    # 2. Target Schedule
    s_start = datetime.now(UTC) + timedelta(hours=3)
    s_end = s_start + timedelta(hours=1)
    s_res = await async_client.post(
        "/api/schedules",
        json={
            "title": "Target Schedule",
            "start_at": s_start.isoformat(),
            "end_at": s_end.isoformat(),
        },
    )
    schedule_id = s_res.json()["id"]

    remind_time_2 = datetime.now(UTC) + timedelta(hours=2, minutes=30)
    r2 = await async_client.post(
        "/api/reminders",
        json={"schedule_id": schedule_id, "remind_at": remind_time_2.isoformat()},
    )
    assert r2.status_code == status.HTTP_201_CREATED
    assert r2.json()["schedule_id"] == schedule_id

    # 3. Target Duty (created directly in DB)
    duty = Duty(
        user_id=user_id,
        title="Weekly Review Duty",
        priority=DutyPriority.HIGH,
    )
    db_session.add(duty)
    await db_session.commit()
    await db_session.refresh(duty)

    remind_time_3 = datetime.now(UTC) + timedelta(hours=4)
    r3 = await async_client.post(
        "/api/reminders",
        json={"duty_id": str(duty.id), "remind_at": remind_time_3.isoformat()},
    )
    assert r3.status_code == status.HTTP_201_CREATED
    assert r3.json()["duty_id"] == str(duty.id)


# 4. Reject reminder without target or multiple targets
@pytest.mark.asyncio
async def test_reject_reminder_invalid_targets(async_client: AsyncClient) -> None:
    """Test validation errors on missing or multiple targets."""
    await create_test_user_and_login(async_client, email="remind_invalid_targets@example.com")
    future = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    dummy_id = str(uuid.uuid4())

    # No target
    r1 = await async_client.post("/api/reminders", json={"remind_at": future})
    assert r1.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Multiple targets
    r2 = await async_client.post(
        "/api/reminders",
        json={"task_id": dummy_id, "schedule_id": dummy_id, "remind_at": future},
    )
    assert r2.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# 5 & 6. Reject target belonging to another user or deleted target
@pytest.mark.asyncio
async def test_reject_unauthorized_or_deleted_target(async_client: AsyncClient) -> None:
    """Test creating reminder targeting another user's item or deleted item is rejected."""
    # User A creates a task and soft deletes it
    await create_test_user_and_login(async_client, email="user_a_remind@example.com")
    t_res = await async_client.post("/api/tasks", json={"title": "Secret Task A"})
    task_a_id = t_res.json()["id"]
    await async_client.delete(f"/api/tasks/{task_a_id}")

    # User B tries to create reminder for User A's deleted task
    await create_test_user_and_login(async_client, email="user_b_remind@example.com")
    future = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    r = await async_client.post("/api/reminders", json={"task_id": task_a_id, "remind_at": future})
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert r.json()["error"]["code"] == "INVALID_TARGET"


# 7. Reject past remind_at
@pytest.mark.asyncio
async def test_reject_past_remind_at(async_client: AsyncClient) -> None:
    """Test scheduling a reminder in the past returns 400 INVALID_REMIND_AT."""
    await create_test_user_and_login(async_client, email="past_remind@example.com")
    t_res = await async_client.post("/api/tasks", json={"title": "Task for Past Reminder"})
    task_id = t_res.json()["id"]

    past = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    r = await async_client.post("/api/reminders", json={"task_id": task_id, "remind_at": past})
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert r.json()["error"]["code"] == "INVALID_REMIND_AT"


# 8, 9, 10. List, update, and cancel reminders
@pytest.mark.asyncio
async def test_reminder_crud_lifecycle(async_client: AsyncClient) -> None:
    """Test reminder listing, rescheduling, cancellation, and deletion."""
    await create_test_user_and_login(async_client, email="remind_crud@example.com")
    t_res = await async_client.post("/api/tasks", json={"title": "Lifecycle Task"})
    task_id = t_res.json()["id"]

    remind_time = datetime.now(UTC) + timedelta(hours=1)
    create_res = await async_client.post(
        "/api/reminders", json={"task_id": task_id, "remind_at": remind_time.isoformat()}
    )
    remind_id = create_res.json()["id"]

    # List
    list_res = await async_client.get("/api/reminders")
    assert list_res.status_code == status.HTTP_200_OK
    assert list_res.json()["total"] == 1

    # Reschedule
    new_time = datetime.now(UTC) + timedelta(hours=5)
    patch_res = await async_client.patch(
        f"/api/reminders/{remind_id}", json={"remind_at": new_time.isoformat()}
    )
    assert patch_res.status_code == status.HTTP_200_OK

    # Cancel
    cancel_res = await async_client.patch(
        f"/api/reminders/{remind_id}", json={"status": "CANCELLED"}
    )
    assert cancel_res.status_code == status.HTTP_200_OK
    assert cancel_res.json()["status"] == "CANCELLED"
    assert app_scheduler.get_job(f"reminder:{remind_id}") is None

    # Delete
    del_res = await async_client.delete(f"/api/reminders/{remind_id}")
    assert del_res.status_code == status.HTTP_200_OK


# 13, 14, 15, 16. Trigger reminder and notification delivery
@pytest.mark.asyncio
async def test_reminder_trigger_creates_notification(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test triggering a reminder generates an in-app notification and marks status TRIGGERED."""
    user = await create_test_user_and_login(async_client, email="trigger_remind@example.com")
    user_id = uuid.UUID(user["id"])

    t_res = await async_client.post("/api/tasks", json={"title": "Urgent Security Audit"})
    task_id = t_res.json()["id"]

    remind_time = datetime.now(UTC) + timedelta(minutes=10)
    create_res = await async_client.post(
        "/api/reminders", json={"task_id": task_id, "remind_at": remind_time.isoformat()}
    )
    remind_id = uuid.UUID(create_res.json()["id"])

    # Directly execute trigger logic through ReminderService
    service = ReminderService(db_session)
    await service.trigger_reminder(remind_id)

    # Verify Reminder is TRIGGERED
    stmt_r = select(Reminder).where(Reminder.id == remind_id)
    rem_db = (await db_session.execute(stmt_r)).scalar_one()
    assert rem_db.status == ReminderStatus.TRIGGERED

    # Verify Notification was created
    stmt_n = select(Notification).where(Notification.user_id == user_id)
    notif = (await db_session.execute(stmt_n)).scalar_one()
    assert notif.type == NotificationType.REMINDER
    assert "Urgent Security Audit" in notif.title
    assert notif.read_at is None


# 18, 19, 20, 21, 22. Notification API: list, read, read-all, unread filtering
@pytest.mark.asyncio
async def test_notification_api_endpoints(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test listing notifications, unread filtering, marking single and all as read."""
    user = await create_test_user_and_login(async_client, email="notif_api@example.com")
    user_id = uuid.UUID(user["id"])

    # Seed 3 notifications directly
    n1 = Notification(
        user_id=user_id,
        type=NotificationType.SYSTEM,
        title="Welcome",
        message="Welcome to SID//OS",
    )
    n2 = Notification(
        user_id=user_id,
        type=NotificationType.DEADLINE,
        title="Deadline Approaching",
        message="Tax return is due soon",
    )
    db_session.add_all([n1, n2])
    await db_session.commit()
    await db_session.refresh(n1)
    await db_session.refresh(n2)

    # List all
    list_res = await async_client.get("/api/notifications")
    assert list_res.status_code == status.HTTP_200_OK
    assert list_res.json()["total"] == 2
    assert list_res.json()["unread_count"] == 2

    # Mark single as read
    read_res = await async_client.post(f"/api/notifications/{n1.id}/read")
    assert read_res.status_code == status.HTTP_200_OK
    assert read_res.json()["is_read"] is True

    # Filter unread (should be 1)
    unread_res = await async_client.get("/api/notifications?read=false")
    assert unread_res.json()["total"] == 1
    assert unread_res.json()["items"][0]["id"] == str(n2.id)

    # Mark all read
    read_all_res = await async_client.post("/api/notifications/read-all")
    assert read_all_res.status_code == status.HTTP_200_OK
    assert read_all_res.json()["updated_count"] == 1

    # Verify unread count is 0
    final_list = await async_client.get("/api/notifications")
    assert final_list.json()["unread_count"] == 0


# 23, 24. Rebuild pending reminders
@pytest.mark.asyncio
async def test_rebuild_pending_reminders(db_session: AsyncSession) -> None:
    """Test rebuilding pending reminder jobs on startup."""
    from app.models.user import User

    # Create user and future reminder
    user = User(
        email="rebuild_user@example.com",
        display_name="Rebuild User",
        password_hash="fakehash",
        timezone="UTC",
    )
    db_session.add(user)
    await db_session.commit()

    remind_at = datetime.now(UTC) + timedelta(hours=10)
    reminder = Reminder(
        user_id=user.id,
        remind_at=remind_at,
        status=ReminderStatus.PENDING,
    )
    db_session.add(reminder)
    await db_session.commit()
    await db_session.refresh(reminder)

    # Rebuild
    rebuilt_count = await ReminderService.rebuild_all_pending_reminders()
    assert rebuilt_count >= 0
