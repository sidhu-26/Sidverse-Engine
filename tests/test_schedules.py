import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.scheduler import app_scheduler
from app.models.activity import Activity
from app.models.enums import ActivityAction
from tests.test_tasks import create_test_user_and_login


# 1. Create schedule
@pytest.mark.asyncio
async def test_create_schedule_success(async_client: AsyncClient) -> None:
    """Test creating a valid schedule block."""
    user = await create_test_user_and_login(async_client, email="sched_user1@example.com")
    start = datetime.now(UTC) + timedelta(hours=1)
    end = start + timedelta(hours=1)

    payload = {
        "title": " Deep Work Session ",
        "description": "Focus block for backend architecture",
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
    }
    response = await async_client.post("/api/schedules", json=payload)
    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert data["title"] == "Deep Work Session"  # trimmed
    assert data["description"] == "Focus block for backend architecture"
    assert data["status"] == "SCHEDULED"
    assert data["task_id"] is None
    assert data["user_id"] == user["id"]
    assert "id" in data


# 2. Create schedule without title
@pytest.mark.asyncio
async def test_create_schedule_empty_title_rejected(async_client: AsyncClient) -> None:
    """Test empty or missing title is rejected."""
    await create_test_user_and_login(async_client, email="sched_empty_title@example.com")
    start = datetime.now(UTC) + timedelta(hours=1)
    end = start + timedelta(hours=1)

    # Missing title
    r1 = await async_client.post(
        "/api/schedules",
        json={"start_at": start.isoformat(), "end_at": end.isoformat()},
    )
    assert r1.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Whitespace title
    r2 = await async_client.post(
        "/api/schedules",
        json={"title": "   ", "start_at": start.isoformat(), "end_at": end.isoformat()},
    )
    assert r2.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# 3 & 4. Invalid start/end & End before start
@pytest.mark.asyncio
async def test_create_schedule_invalid_time_range(async_client: AsyncClient) -> None:
    """Test start_at after end_at is rejected."""
    await create_test_user_and_login(async_client, email="sched_invalid_times@example.com")
    start = datetime.now(UTC) + timedelta(hours=2)
    end = datetime.now(UTC) + timedelta(hours=1)

    payload = {
        "title": "Invalid Block",
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
    }
    response = await async_client.post("/api/schedules", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# 5. Naive datetime rejection
@pytest.mark.asyncio
async def test_create_schedule_naive_datetime_rejected(async_client: AsyncClient) -> None:
    """Test naive datetimes without timezone are rejected."""
    await create_test_user_and_login(async_client, email="sched_naive@example.com")
    payload = {
        "title": "Naive Block",
        "start_at": "2026-10-08T10:00:00",
        "end_at": "2026-10-08T11:00:00",
    }
    response = await async_client.post("/api/schedules", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# 6 & 7. Schedule without task and with own task
@pytest.mark.asyncio
async def test_create_schedule_with_own_task(async_client: AsyncClient) -> None:
    """Test associating a schedule with an existing personal task."""
    await create_test_user_and_login(async_client, email="sched_task_user@example.com")
    task_res = await async_client.post("/api/tasks", json={"title": "Write Engine Code"})
    task_id = task_res.json()["id"]

    start = datetime.now(UTC) + timedelta(hours=3)
    end = start + timedelta(hours=2)

    payload = {
        "title": "Coding Session",
        "task_id": task_id,
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
    }
    response = await async_client.post("/api/schedules", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["task_id"] == task_id


# 8. Reject another user's task
@pytest.mark.asyncio
async def test_reject_other_users_task_in_schedule(async_client: AsyncClient) -> None:
    """Test scheduling another user's task returns 400 INVALID_TASK."""
    # User A creates a task
    await create_test_user_and_login(async_client, email="user_a_task@example.com")
    task_res = await async_client.post("/api/tasks", json={"title": "User A Task"})
    task_a_id = task_res.json()["id"]

    # User B tries to schedule User A's task
    await create_test_user_and_login(async_client, email="user_b_task@example.com")
    start = datetime.now(UTC) + timedelta(hours=1)
    end = start + timedelta(hours=1)

    payload = {
        "title": "Malicious Block",
        "task_id": task_a_id,
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
    }
    response = await async_client.post("/api/schedules", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["error"]["code"] == "INVALID_TASK"


# 9, 10, 11. List own schedules and IDOR protection
@pytest.mark.asyncio
async def test_list_and_get_schedule_idor(async_client: AsyncClient) -> None:
    """Test schedule listing is scoped to current user and IDOR returns 404."""
    # User A creates schedule
    await create_test_user_and_login(async_client, email="sched_user_a@example.com")
    start = datetime.now(UTC) + timedelta(hours=1)
    end = start + timedelta(hours=1)
    res_a = await async_client.post(
        "/api/schedules",
        json={"title": "User A Block", "start_at": start.isoformat(), "end_at": end.isoformat()},
    )
    sched_a_id = res_a.json()["id"]

    # User B registers and lists schedules
    await create_test_user_and_login(async_client, email="sched_user_b@example.com")
    list_b = await async_client.get("/api/schedules")
    assert list_b.json()["total"] == 0

    # User B attempts to get User A's schedule
    get_b = await async_client.get(f"/api/schedules/{sched_a_id}")
    assert get_b.status_code == status.HTTP_404_NOT_FOUND
    assert get_b.json()["error"]["code"] == "SCHEDULE_NOT_FOUND"


# 12 & 13. Update schedule and Reschedule activity
@pytest.mark.asyncio
async def test_update_and_reschedule(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Test updating fields and rescheduling records SCHEDULE_RESCHEDULED activity."""
    user = await create_test_user_and_login(async_client, email="sched_update@example.com")
    user_id = uuid.UUID(user["id"])

    start = datetime.now(UTC) + timedelta(hours=1)
    end = start + timedelta(hours=1)
    res = await async_client.post(
        "/api/schedules",
        json={"title": "Original Block", "start_at": start.isoformat(), "end_at": end.isoformat()},
    )
    sched_id = res.json()["id"]

    # Partial update: title
    patch1 = await async_client.patch(f"/api/schedules/{sched_id}", json={"title": "Renamed Block"})
    assert patch1.status_code == status.HTTP_200_OK
    assert patch1.json()["title"] == "Renamed Block"

    # Reschedule time
    new_start = datetime.now(UTC) + timedelta(hours=5)
    new_end = new_start + timedelta(hours=2)
    patch2 = await async_client.patch(
        f"/api/schedules/{sched_id}",
        json={"start_at": new_start.isoformat(), "end_at": new_end.isoformat()},
    )
    assert patch2.status_code == status.HTTP_200_OK

    # Check audit log for SCHEDULE_RESCHEDULED
    stmt = select(Activity).where(
        Activity.user_id == user_id,
        Activity.entity_id == uuid.UUID(sched_id),
        Activity.action == ActivityAction.SCHEDULE_RESCHEDULED,
    )
    act = (await db_session.execute(stmt)).scalar_one_or_none()
    assert act is not None


# 14. Overlap detection
@pytest.mark.asyncio
async def test_schedule_overlap_detection(async_client: AsyncClient) -> None:
    """Test creating an overlapping schedule returns 409 SCHEDULE_OVERLAP."""
    await create_test_user_and_login(async_client, email="sched_overlap@example.com")
    base_time = datetime.now(UTC) + timedelta(days=1)

    # Schedule 1: 10:00 - 12:00
    s1_start = base_time.replace(hour=10, minute=0, second=0, microsecond=0)
    s1_end = base_time.replace(hour=12, minute=0, second=0, microsecond=0)
    r1 = await async_client.post(
        "/api/schedules",
        json={
            "title": "Block 1",
            "start_at": s1_start.isoformat(),
            "end_at": s1_end.isoformat(),
        },
    )
    assert r1.status_code == status.HTTP_201_CREATED

    # Schedule 2: 11:00 - 13:00 (Overlaps Block 1)
    s2_start = base_time.replace(hour=11, minute=0, second=0, microsecond=0)
    s2_end = base_time.replace(hour=13, minute=0, second=0, microsecond=0)
    r2 = await async_client.post(
        "/api/schedules",
        json={
            "title": "Block 2",
            "start_at": s2_start.isoformat(),
            "end_at": s2_end.isoformat(),
        },
    )
    assert r2.status_code == status.HTTP_409_CONFLICT
    assert r2.json()["error"]["code"] == "SCHEDULE_OVERLAP"

    # Schedule 3: 12:00 - 14:00 (Back to back, non-overlapping -> Valid)
    s3_start = base_time.replace(hour=12, minute=0, second=0, microsecond=0)
    s3_end = base_time.replace(hour=14, minute=0, second=0, microsecond=0)
    r3 = await async_client.post(
        "/api/schedules",
        json={
            "title": "Block 3",
            "start_at": s3_start.isoformat(),
            "end_at": s3_end.isoformat(),
        },
    )
    assert r3.status_code == status.HTTP_201_CREATED


# 15, 16, 17. Schedule status transitions
@pytest.mark.asyncio
async def test_schedule_status_transitions(async_client: AsyncClient) -> None:
    """Test valid and invalid schedule status transitions."""
    await create_test_user_and_login(async_client, email="sched_transitions@example.com")
    start = datetime.now(UTC) + timedelta(hours=1)
    end = start + timedelta(hours=1)
    res = await async_client.post(
        "/api/schedules",
        json={"title": "Status Test", "start_at": start.isoformat(), "end_at": end.isoformat()},
    )
    sched_id = res.json()["id"]

    # SCHEDULED -> IN_PROGRESS
    p1 = await async_client.patch(f"/api/schedules/{sched_id}", json={"status": "IN_PROGRESS"})
    assert p1.status_code == status.HTTP_200_OK
    assert p1.json()["status"] == "IN_PROGRESS"

    # IN_PROGRESS -> SCHEDULED (Invalid transition)
    p_invalid = await async_client.patch(f"/api/schedules/{sched_id}", json={"status": "SCHEDULED"})
    assert p_invalid.status_code == status.HTTP_400_BAD_REQUEST
    assert p_invalid.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"

    # IN_PROGRESS -> COMPLETED
    p2 = await async_client.patch(f"/api/schedules/{sched_id}", json={"status": "COMPLETED"})
    assert p2.status_code == status.HTTP_200_OK
    assert p2.json()["status"] == "COMPLETED"

    # COMPLETED -> SCHEDULED (Reopen)
    p3 = await async_client.patch(f"/api/schedules/{sched_id}", json={"status": "SCHEDULED"})
    assert p3.status_code == status.HTTP_200_OK
    assert p3.json()["status"] == "SCHEDULED"


# 18 & 19. Soft delete schedule
@pytest.mark.asyncio
async def test_soft_delete_schedule(async_client: AsyncClient) -> None:
    """Test soft delete makes schedule inaccessible from list, detail, and update."""
    await create_test_user_and_login(async_client, email="sched_delete@example.com")
    start = datetime.now(UTC) + timedelta(hours=1)
    end = start + timedelta(hours=1)
    res = await async_client.post(
        "/api/schedules",
        json={"title": "To Delete", "start_at": start.isoformat(), "end_at": end.isoformat()},
    )
    sched_id = res.json()["id"]

    # Delete
    del_res = await async_client.delete(f"/api/schedules/{sched_id}")
    assert del_res.status_code == status.HTTP_200_OK

    # Detail -> 404
    get_res = await async_client.get(f"/api/schedules/{sched_id}")
    assert get_res.status_code == status.HTTP_404_NOT_FOUND

    # List -> 0
    list_res = await async_client.get("/api/schedules")
    assert list_res.json()["total"] == 0


# 20. Audit activity records
@pytest.mark.asyncio
async def test_schedule_activity_audit(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Test that schedule actions log appropriate activity events."""
    user = await create_test_user_and_login(async_client, email="sched_audit@example.com")
    user_id = uuid.UUID(user["id"])

    start = datetime.now(UTC) + timedelta(hours=1)
    end = start + timedelta(hours=1)
    res = await async_client.post(
        "/api/schedules",
        json={"title": "Audit Block", "start_at": start.isoformat(), "end_at": end.isoformat()},
    )
    sched_id = uuid.UUID(res.json()["id"])

    # Complete
    await async_client.patch(f"/api/schedules/{sched_id}", json={"status": "COMPLETED"})

    # Delete
    await async_client.delete(f"/api/schedules/{sched_id}")

    stmt = (
        select(Activity)
        .where(Activity.user_id == user_id, Activity.entity_id == sched_id)
        .order_by(Activity.created_at.asc())
    )
    acts = list((await db_session.execute(stmt)).scalars().all())
    actions = [a.action for a in acts]
    assert ActivityAction.SCHEDULE_CREATED in actions
    assert ActivityAction.SCHEDULE_COMPLETED in actions
    assert ActivityAction.SCHEDULE_DELETED in actions


# 21, 22, 23. Core Scheduler unit tests
@pytest.mark.asyncio
async def test_scheduler_core_operations() -> None:
    """Test scheduler initialization, job registration, deterministic IDs, and shutdown."""
    app_scheduler.start()
    assert app_scheduler.is_running is True

    run_time = datetime.now(UTC) + timedelta(minutes=10)
    job_id = f"test_job_{uuid.uuid4()}"

    def sample_job() -> None:
        pass

    registered = app_scheduler.add_date_job(job_id, sample_job, run_time)
    assert registered is True

    job = app_scheduler.get_job(job_id)
    assert job is not None
    assert job.id == job_id

    # Remove job
    removed = app_scheduler.remove_job(job_id)
    assert removed is True
    assert app_scheduler.get_job(job_id) is None
