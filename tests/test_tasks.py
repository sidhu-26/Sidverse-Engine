import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.models.activity import Activity
from app.models.enums import (
    ActivityAction,
    ProjectPriority,
    ProjectStatus,
)
from app.models.project import Project


async def create_test_user_and_login(
    client: AsyncClient,
    email: str = "user@example.com",
    display_name: str = "Test User",
    password: str = "TestPassword123!",
) -> dict:
    """Helper to register and login a user, setting the session cookie on the client."""
    payload = {
        "email": email,
        "display_name": display_name,
        "password": password,
        "timezone": "UTC",
    }
    response = await client.post("/api/auth/register", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["user"]


# 1. Create task
@pytest.mark.asyncio
async def test_create_task_success(async_client: AsyncClient) -> None:
    """Test creating a valid task returns 201 with correctly populated fields."""
    user = await create_test_user_and_login(async_client, email="create_task@example.com")

    payload = {
        "title": "  Build Task Engine  ",
        "description": "Implement core task business rules",
        "priority": "HIGH",
        "estimated_minutes": 45,
    }
    response = await async_client.post("/api/tasks", json=payload)
    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert data["title"] == "Build Task Engine"  # trimmed
    assert data["description"] == "Implement core task business rules"
    assert data["priority"] == "HIGH"
    assert data["status"] == "TODO"
    assert data["estimated_minutes"] == 45
    assert data["user_id"] == user["id"]
    assert data["completed_at"] is None
    assert data["is_overdue"] is False
    assert "id" in data
    assert "created_at" in data


# 2. Create task without title / empty title
@pytest.mark.asyncio
async def test_create_task_empty_title_rejected(async_client: AsyncClient) -> None:
    """Test creating a task with empty/whitespace-only title is rejected."""
    await create_test_user_and_login(async_client, email="empty_title@example.com")

    # Missing title
    r1 = await async_client.post("/api/tasks", json={"description": "No title"})
    assert r1.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Whitespace title
    r2 = await async_client.post("/api/tasks", json={"title": "   ", "description": "Blank title"})
    assert r2.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# 3. Create task with invalid priority
@pytest.mark.asyncio
async def test_create_task_invalid_priority(async_client: AsyncClient) -> None:
    """Test creating a task with invalid priority fails validation."""
    await create_test_user_and_login(async_client, email="invalid_priority@example.com")

    payload = {"title": "Sample Task", "priority": "SUPER_URGENT"}
    response = await async_client.post("/api/tasks", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# 4. Create task with invalid estimated_minutes (<= 0)
@pytest.mark.asyncio
async def test_create_task_invalid_estimated_minutes(async_client: AsyncClient) -> None:
    """Test estimated_minutes must be positive."""
    await create_test_user_and_login(async_client, email="invalid_est@example.com")

    r1 = await async_client.post("/api/tasks", json={"title": "Task 1", "estimated_minutes": 0})
    assert r1.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    r2 = await async_client.post("/api/tasks", json={"title": "Task 2", "estimated_minutes": -10})
    assert r2.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# 5. Create task with invalid project
@pytest.mark.asyncio
async def test_create_task_nonexistent_project(async_client: AsyncClient) -> None:
    """Test creating a task with a non-existent project_id returns 400."""
    await create_test_user_and_login(async_client, email="nonexistent_proj@example.com")

    payload = {"title": "Task with fake project", "project_id": str(uuid.uuid4())}
    response = await async_client.post("/api/tasks", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert data["error"]["code"] == "INVALID_PROJECT"


# 6. Create task for another user's project
@pytest.mark.asyncio
async def test_create_task_other_user_project(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test a user cannot assign a task to another user's project."""
    # User A registers and creates a project directly in DB
    user_a = await create_test_user_and_login(async_client, email="user_a_proj@example.com")
    project_a = Project(
        user_id=uuid.UUID(user_a["id"]),
        name="User A Secret Project",
        status=ProjectStatus.ACTIVE,
        priority=ProjectPriority.MEDIUM,
    )
    db_session.add(project_a)
    await db_session.commit()
    await db_session.refresh(project_a)

    # User B registers
    await create_test_user_and_login(async_client, email="user_b_proj@example.com")

    # User B tries to create task pointing to User A's project
    payload = {"title": "User B Task", "project_id": str(project_a.id)}
    response = await async_client.post("/api/tasks", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["error"]["code"] == "INVALID_PROJECT"


# 7 & 8. List own tasks and exclude another user's tasks
@pytest.mark.asyncio
async def test_list_tasks_scoped_to_current_user(async_client: AsyncClient) -> None:
    """Test listing tasks only returns the authenticated user's tasks."""
    # User A creates 2 tasks
    await create_test_user_and_login(async_client, email="user_a_list@example.com")
    await async_client.post("/api/tasks", json={"title": "User A Task 1", "priority": "HIGH"})
    await async_client.post("/api/tasks", json={"title": "User A Task 2", "priority": "LOW"})

    # User B creates 1 task
    await create_test_user_and_login(async_client, email="user_b_list@example.com")
    await async_client.post("/api/tasks", json={"title": "User B Task 1", "priority": "URGENT"})

    # User B lists tasks
    res_b = await async_client.get("/api/tasks")
    assert res_b.status_code == status.HTTP_200_OK
    data_b = res_b.json()
    assert data_b["total"] == 1
    assert len(data_b["items"]) == 1
    assert data_b["items"][0]["title"] == "User B Task 1"

    # User A logs in again and lists tasks
    await async_client.post(
        "/api/auth/login",
        json={"email": "user_a_list@example.com", "password": "TestPassword123!"},
    )
    res_a = await async_client.get("/api/tasks")
    assert res_a.status_code == status.HTTP_200_OK
    data_a = res_a.json()
    assert data_a["total"] == 2
    titles = [t["title"] for t in data_a["items"]]
    assert "User A Task 1" in titles
    assert "User A Task 2" in titles
    assert "User B Task 1" not in titles


# 9 & 10. Get own task & IDOR protection
@pytest.mark.asyncio
async def test_get_task_and_idor_protection(async_client: AsyncClient) -> None:
    """Test retrieving task detail and IDOR protection returning 404 for other user's task."""
    await create_test_user_and_login(async_client, email="user_owner@example.com")
    create_res = await async_client.post("/api/tasks", json={"title": "Owner Task"})
    task_id = create_res.json()["id"]

    # Owner gets detail
    get_res = await async_client.get(f"/api/tasks/{task_id}")
    assert get_res.status_code == status.HTTP_200_OK
    assert get_res.json()["id"] == task_id
    assert get_res.json()["title"] == "Owner Task"

    # Attacker logs in and attempts to access owner's task
    await create_test_user_and_login(async_client, email="user_attacker@example.com")
    attacker_get = await async_client.get(f"/api/tasks/{task_id}")
    assert attacker_get.status_code == status.HTTP_404_NOT_FOUND
    assert attacker_get.json()["error"]["code"] == "TASK_NOT_FOUND"


# 11 & 12. Update task and partial update
@pytest.mark.asyncio
async def test_update_task_partial(async_client: AsyncClient) -> None:
    """Test partial updates modify only specified fields."""
    await create_test_user_and_login(async_client, email="update_task@example.com")
    task_res = await async_client.post(
        "/api/tasks",
        json={"title": "Initial Title", "description": "Initial Desc", "priority": "LOW"},
    )
    task_id = task_res.json()["id"]

    # Update only priority and title
    patch_res = await async_client.patch(
        f"/api/tasks/{task_id}",
        json={"title": "Updated Title", "priority": "URGENT"},
    )
    assert patch_res.status_code == status.HTTP_200_OK
    updated_data = patch_res.json()
    assert updated_data["title"] == "Updated Title"
    assert updated_data["description"] == "Initial Desc"  # Preserved
    assert updated_data["priority"] == "URGENT"


# 13. Invalid status transitions
@pytest.mark.asyncio
async def test_invalid_status_transitions(async_client: AsyncClient) -> None:
    """Test rejected status transitions return 400 INVALID_STATUS_TRANSITION."""
    await create_test_user_and_login(async_client, email="transitions@example.com")
    t1 = await async_client.post("/api/tasks", json={"title": "Transition Test"})
    task_id = t1.json()["id"]

    # Cancel task (TODO -> CANCELLED: valid)
    cancel_res = await async_client.patch(f"/api/tasks/{task_id}", json={"status": "CANCELLED"})
    assert cancel_res.status_code == status.HTTP_200_OK
    assert cancel_res.json()["status"] == "CANCELLED"

    # CANCELLED -> COMPLETED is invalid (only CANCELLED -> TODO is valid)
    invalid_res = await async_client.patch(f"/api/tasks/{task_id}", json={"status": "COMPLETED"})
    assert invalid_res.status_code == status.HTTP_400_BAD_REQUEST
    assert invalid_res.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"

    # Reopen to TODO (CANCELLED -> TODO: valid)
    reopen_res = await async_client.patch(f"/api/tasks/{task_id}", json={"status": "TODO"})
    assert reopen_res.status_code == status.HTTP_200_OK

    # Complete task (TODO -> COMPLETED: valid)
    complete_res = await async_client.patch(f"/api/tasks/{task_id}", json={"status": "COMPLETED"})
    assert complete_res.status_code == status.HTTP_200_OK

    # COMPLETED -> CANCELLED is invalid (only COMPLETED -> TODO or IN_PROGRESS is valid)
    invalid_res2 = await async_client.patch(f"/api/tasks/{task_id}", json={"status": "CANCELLED"})
    assert invalid_res2.status_code == status.HTTP_400_BAD_REQUEST
    assert invalid_res2.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"


# 14 & 15. Complete task and completed_at is populated
@pytest.mark.asyncio
async def test_task_completion_sets_completed_at(async_client: AsyncClient) -> None:
    """Test completing a task populates completed_at."""
    await create_test_user_and_login(async_client, email="complete_test@example.com")
    task_res = await async_client.post("/api/tasks", json={"title": "Complete Me"})
    task_id = task_res.json()["id"]
    assert task_res.json()["completed_at"] is None

    patch_res = await async_client.patch(f"/api/tasks/{task_id}", json={"status": "COMPLETED"})
    assert patch_res.status_code == status.HTTP_200_OK
    data = patch_res.json()
    assert data["status"] == "COMPLETED"
    assert data["completed_at"] is not None


# 16 & 17. Reopen completed task and completed_at is cleared
@pytest.mark.asyncio
async def test_task_reopening_clears_completed_at(async_client: AsyncClient) -> None:
    """Test reopening a completed task resets completed_at to None."""
    await create_test_user_and_login(async_client, email="reopen_test@example.com")
    task_res = await async_client.post("/api/tasks", json={"title": "Reopen Me"})
    task_id = task_res.json()["id"]

    # Complete
    await async_client.patch(f"/api/tasks/{task_id}", json={"status": "COMPLETED"})

    # Reopen to IN_PROGRESS
    reopen_res = await async_client.patch(f"/api/tasks/{task_id}", json={"status": "IN_PROGRESS"})
    assert reopen_res.status_code == status.HTTP_200_OK
    data = reopen_res.json()
    assert data["status"] == "IN_PROGRESS"
    assert data["completed_at"] is None


# 18. Cancel task (completed_at remains None)
@pytest.mark.asyncio
async def test_cancel_task_completed_at_none(async_client: AsyncClient) -> None:
    """Test cancelling a task keeps completed_at as None."""
    await create_test_user_and_login(async_client, email="cancel_test@example.com")
    task_res = await async_client.post("/api/tasks", json={"title": "Cancel Me"})
    task_id = task_res.json()["id"]

    cancel_res = await async_client.patch(f"/api/tasks/{task_id}", json={"status": "CANCELLED"})
    assert cancel_res.status_code == status.HTTP_200_OK
    assert cancel_res.json()["status"] == "CANCELLED"
    assert cancel_res.json()["completed_at"] is None


# 19, 20, 21. Overdue task logic
@pytest.mark.asyncio
async def test_overdue_task_detection(async_client: AsyncClient) -> None:
    """Test overdue calculation for active, completed, and cancelled tasks."""
    await create_test_user_and_login(async_client, email="overdue_test@example.com")
    past_time = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    future_time = (datetime.now(UTC) + timedelta(hours=24)).isoformat()

    # Task 1: Past due date, status TODO -> Overdue
    t1 = await async_client.post("/api/tasks", json={"title": "Overdue Task", "due_at": past_time})
    assert t1.json()["is_overdue"] is True

    # Task 2: Future due date, status TODO -> Not overdue
    t2 = await async_client.post("/api/tasks", json={"title": "Future Task", "due_at": future_time})
    assert t2.json()["is_overdue"] is False

    # Task 3: Past due date, but COMPLETED -> Not overdue
    t3 = await async_client.post(
        "/api/tasks", json={"title": "Completed Past Task", "due_at": past_time}
    )
    t3_id = t3.json()["id"]
    t3_completed = await async_client.patch(f"/api/tasks/{t3_id}", json={"status": "COMPLETED"})
    assert t3_completed.json()["is_overdue"] is False

    # Task 4: Past due date, but CANCELLED -> Not overdue
    t4 = await async_client.post(
        "/api/tasks", json={"title": "Cancelled Past Task", "due_at": past_time}
    )
    t4_id = t4.json()["id"]
    t4_cancelled = await async_client.patch(f"/api/tasks/{t4_id}", json={"status": "CANCELLED"})
    assert t4_cancelled.json()["is_overdue"] is False

    # Test filtering by overdue=true
    overdue_list = await async_client.get("/api/tasks?overdue=true")
    assert overdue_list.status_code == status.HTTP_200_OK
    assert overdue_list.json()["total"] == 1
    assert overdue_list.json()["items"][0]["title"] == "Overdue Task"


# 22, 23, 24. Soft delete and isolation
@pytest.mark.asyncio
async def test_soft_delete_task(async_client: AsyncClient) -> None:
    """Test soft delete makes task inaccessible from list, detail, and update."""
    await create_test_user_and_login(async_client, email="delete_test@example.com")
    task_res = await async_client.post("/api/tasks", json={"title": "To be deleted"})
    task_id = task_res.json()["id"]

    # Delete task
    del_res = await async_client.delete(f"/api/tasks/{task_id}")
    assert del_res.status_code == status.HTTP_200_OK

    # Task should not appear in list
    list_res = await async_client.get("/api/tasks")
    assert list_res.json()["total"] == 0

    # Detail should return 404
    get_res = await async_client.get(f"/api/tasks/{task_id}")
    assert get_res.status_code == status.HTTP_404_NOT_FOUND

    # Update should return 404
    patch_res = await async_client.patch(
        f"/api/tasks/{task_id}", json={"title": "Cannot update deleted"}
    )
    assert patch_res.status_code == status.HTTP_404_NOT_FOUND


# 25, 26, 27, 28, 29. Activity audit logging
@pytest.mark.asyncio
async def test_activity_audit_logs(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Test that all task lifecycle actions create appropriate activity audit records."""
    user = await create_test_user_and_login(async_client, email="audit_test@example.com")
    user_id = uuid.UUID(user["id"])

    # 1. TASK_CREATED
    t_res = await async_client.post(
        "/api/tasks",
        json={"title": "Audit Task", "priority": "HIGH"},
    )
    task_id = uuid.UUID(t_res.json()["id"])

    # 2. TASK_RESCHEDULED
    new_due = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    await async_client.patch(f"/api/tasks/{task_id}", json={"due_at": new_due})

    # 3. TASK_COMPLETED
    await async_client.patch(f"/api/tasks/{task_id}", json={"status": "COMPLETED"})

    # 4. TASK_REOPENED
    await async_client.patch(f"/api/tasks/{task_id}", json={"status": "TODO"})

    # 5. TASK_DELETED
    await async_client.delete(f"/api/tasks/{task_id}")

    # Inspect activities in DB
    stmt = (
        select(Activity)
        .where(Activity.user_id == user_id, Activity.entity_id == task_id)
        .order_by(Activity.created_at.asc())
    )
    activities = list((await db_session.execute(stmt)).scalars().all())
    actions = [a.action for a in activities]

    assert ActivityAction.TASK_CREATED in actions
    assert ActivityAction.TASK_RESCHEDULED in actions
    assert ActivityAction.TASK_COMPLETED in actions
    assert ActivityAction.TASK_REOPENED in actions
    assert ActivityAction.TASK_DELETED in actions


# 30. Authentication required for every task endpoint
@pytest.mark.asyncio
async def test_task_endpoints_require_authentication(async_client: AsyncClient) -> None:
    """Test all task endpoints return 401 UNAUTHORIZED when unauthenticated."""
    fake_id = uuid.uuid4()

    # POST /api/tasks
    r1 = await async_client.post("/api/tasks", json={"title": "Unauthenticated Task"})
    assert r1.status_code == status.HTTP_401_UNAUTHORIZED

    # GET /api/tasks
    r2 = await async_client.get("/api/tasks")
    assert r2.status_code == status.HTTP_401_UNAUTHORIZED

    # GET /api/tasks/{id}
    r3 = await async_client.get(f"/api/tasks/{fake_id}")
    assert r3.status_code == status.HTTP_401_UNAUTHORIZED

    # PATCH /api/tasks/{id}
    r4 = await async_client.patch(f"/api/tasks/{fake_id}", json={"title": "New Title"})
    assert r4.status_code == status.HTTP_401_UNAUTHORIZED

    # DELETE /api/tasks/{id}
    r5 = await async_client.delete(f"/api/tasks/{fake_id}")
    assert r5.status_code == status.HTTP_401_UNAUTHORIZED
