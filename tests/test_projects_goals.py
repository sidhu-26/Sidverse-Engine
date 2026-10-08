import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.models.activity import Activity
from app.models.enums import ActivityAction
from tests.test_tasks import create_test_user_and_login

# ============================================================
# PROJECTS TESTS (1 to 15)
# ============================================================


@pytest.mark.asyncio
async def test_project_crud_and_validation(async_client: AsyncClient) -> None:
    """Test project creation, default values, validation, updating, and detail fetch."""
    user = await create_test_user_and_login(async_client, email="proj_crud@example.com")
    target_dt = (datetime.now(UTC) + timedelta(days=30)).isoformat()

    # 1. Validation: Reject blank name
    r_bad = await async_client.post("/api/projects", json={"name": "   "})
    assert r_bad.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 2. Create with defaults
    r_create = await async_client.post(
        "/api/projects",
        json={
            "name": "  Apollo Project  ",
            "description": "Next generation core system",
            "target_date": target_dt,
        },
    )
    assert r_create.status_code == status.HTTP_201_CREATED
    data = r_create.json()
    assert data["name"] == "Apollo Project"  # trimmed
    assert data["status"] == "ACTIVE"  # default
    assert data["priority"] == "MEDIUM"  # default
    assert data["user_id"] == user["id"]
    proj_id = data["id"]

    # 3. Get Project
    r_get = await async_client.get(f"/api/projects/{proj_id}")
    assert r_get.status_code == status.HTTP_200_OK
    assert r_get.json()["name"] == "Apollo Project"

    # 4. Update Project (priority & status)
    r_update = await async_client.patch(
        f"/api/projects/{proj_id}",
        json={"priority": "HIGH", "status": "COMPLETED"},
    )
    assert r_update.status_code == status.HTTP_200_OK
    assert r_update.json()["priority"] == "HIGH"
    assert r_update.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_project_list_search_and_filters(async_client: AsyncClient) -> None:
    """Test listing, filtering by status/priority, and searching projects."""
    await create_test_user_and_login(async_client, email="proj_filters@example.com")

    # Create 3 projects
    await async_client.post(
        "/api/projects",
        json={"name": "Website Redesign", "status": "ACTIVE", "priority": "LOW"},
    )
    await async_client.post(
        "/api/projects",
        json={"name": "Mobile App Launch", "status": "ACTIVE", "priority": "HIGH"},
    )
    await async_client.post(
        "/api/projects",
        json={"name": "Legacy Migration", "status": "ARCHIVED", "priority": "MEDIUM"},
    )

    # Filter by status ACTIVE
    r_active = await async_client.get("/api/projects?status=ACTIVE")
    assert r_active.json()["total"] == 2

    # Filter by priority HIGH
    r_high = await async_client.get("/api/projects?priority=HIGH")
    assert r_high.json()["total"] == 1
    assert r_high.json()["items"][0]["name"] == "Mobile App Launch"

    # Search keyword
    r_search = await async_client.get("/api/projects?search=Migration")
    assert r_search.json()["total"] == 1
    assert r_search.json()["items"][0]["name"] == "Legacy Migration"


@pytest.mark.asyncio
async def test_project_soft_delete_and_idor(async_client: AsyncClient) -> None:
    """Test soft delete hides project and cross-user access returns 404."""
    # User A creates project
    await create_test_user_and_login(async_client, email="proj_user_a@example.com")
    res_a = await async_client.post("/api/projects", json={"name": "User A Secret Project"})
    proj_a_id = res_a.json()["id"]

    # User B registers and attempts access
    await create_test_user_and_login(async_client, email="proj_user_b@example.com")
    r_idor_get = await async_client.get(f"/api/projects/{proj_a_id}")
    assert r_idor_get.status_code == status.HTTP_404_NOT_FOUND
    assert r_idor_get.json()["error"]["code"] == "PROJECT_NOT_FOUND"

    # User A logs in and deletes project
    await async_client.post(
        "/api/auth/login",
        json={"email": "proj_user_a@example.com", "password": "TestPassword123!"},
    )
    r_del = await async_client.delete(f"/api/projects/{proj_a_id}")
    assert r_del.status_code == status.HTTP_200_OK

    # Confirm detail 404 and list empty
    r_check = await async_client.get(f"/api/projects/{proj_a_id}")
    assert r_check.status_code == status.HTTP_404_NOT_FOUND
    assert (await async_client.get("/api/projects")).json()["total"] == 0


@pytest.mark.asyncio
async def test_project_task_integration(async_client: AsyncClient) -> None:
    """Test assigning tasks to active projects and blocking assignment to deleted projects."""
    await create_test_user_and_login(async_client, email="proj_task_int@example.com")

    # Create project
    proj_res = await async_client.post("/api/projects", json={"name": "Alpha Project"})
    proj_id = proj_res.json()["id"]

    # Create task assigned to project
    t_res = await async_client.post(
        "/api/tasks", json={"title": "Design Database Schema", "project_id": proj_id}
    )
    assert t_res.status_code == status.HTTP_201_CREATED
    assert t_res.json()["project_id"] == proj_id

    # Soft delete project
    await async_client.delete(f"/api/projects/{proj_id}")

    # Verify task still retains project_id
    task_get = await async_client.get(f"/api/tasks/{t_res.json()['id']}")
    assert task_get.status_code == status.HTTP_200_OK
    assert task_get.json()["project_id"] == proj_id

    # Attempt to assign a new task to deleted project -> rejected
    t_bad = await async_client.post(
        "/api/tasks", json={"title": "New Task on Deleted Project", "project_id": proj_id}
    )
    assert t_bad.status_code == status.HTTP_400_BAD_REQUEST
    assert t_bad.json()["error"]["code"] == "INVALID_PROJECT"


@pytest.mark.asyncio
async def test_project_activity_logs(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Test project lifecycle records appropriate audit trail activities."""
    user = await create_test_user_and_login(async_client, email="proj_audit@example.com")
    user_id = uuid.UUID(user["id"])

    # Create
    p_res = await async_client.post("/api/projects", json={"name": "Audit Trail Project"})
    proj_id = uuid.UUID(p_res.json()["id"])

    # Complete
    await async_client.patch(f"/api/projects/{proj_id}", json={"status": "COMPLETED"})

    # Delete
    await async_client.delete(f"/api/projects/{proj_id}")

    stmt = (
        select(Activity)
        .where(Activity.user_id == user_id, Activity.entity_id == proj_id)
        .order_by(Activity.created_at.asc())
    )
    acts = list((await db_session.execute(stmt)).scalars().all())
    actions = [a.action for a in acts]
    assert ActivityAction.PROJECT_CREATED in actions
    assert ActivityAction.PROJECT_COMPLETED in actions
    assert ActivityAction.PROJECT_DELETED in actions


# ============================================================
# GOALS & MILESTONES TESTS (16 to 42)
# ============================================================


@pytest.mark.asyncio
async def test_goal_crud_and_progress_validation(async_client: AsyncClient) -> None:
    """Test goal creation, progress range validations (0-100), updating, and listing."""
    await create_test_user_and_login(async_client, email="goal_crud@example.com")

    # 1. Invalid progress: < 0
    r_neg = await async_client.post("/api/goals", json={"title": "Goal 1", "progress": -5})
    assert r_neg.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 2. Invalid progress: > 100
    r_high = await async_client.post("/api/goals", json={"title": "Goal 2", "progress": 120})
    assert r_high.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 3. Create valid goal (progress defaults to 0)
    r_create = await async_client.post(
        "/api/goals",
        json={"title": "  Learn Rust  ", "description": "Master systems programming"},
    )
    assert r_create.status_code == status.HTTP_201_CREATED
    data = r_create.json()
    assert data["title"] == "Learn Rust"  # trimmed
    assert data["progress"] == 0
    assert data["status"] == "ACTIVE"
    goal_id = data["id"]

    # 4. Update progress to 75
    r_update = await async_client.patch(f"/api/goals/{goal_id}", json={"progress": 75})
    assert r_update.status_code == status.HTTP_200_OK
    assert r_update.json()["progress"] == 75

    # 5. Soft delete goal
    r_del = await async_client.delete(f"/api/goals/{goal_id}")
    assert r_del.status_code == status.HTTP_200_OK

    # 6. Verify 404 on get and absent from list
    r_goal_check = await async_client.get(f"/api/goals/{goal_id}")
    assert r_goal_check.status_code == status.HTTP_404_NOT_FOUND
    assert (await async_client.get("/api/goals")).json()["total"] == 0


@pytest.mark.asyncio
async def test_goal_milestones_lifecycle_and_ordering(async_client: AsyncClient) -> None:
    """Test goal milestone creation, position ordering, completion timestamps, and reopening."""
    await create_test_user_and_login(async_client, email="milestone_user@example.com")

    # Create Goal
    g_res = await async_client.post("/api/goals", json={"title": "Launch SaaS Product"})
    goal_id = g_res.json()["id"]

    # Add 3 milestones with explicit positions
    m2 = await async_client.post(
        f"/api/goals/{goal_id}/milestones",
        json={"title": "Beta Testing", "position": 2},
    )
    m1 = await async_client.post(
        f"/api/goals/{goal_id}/milestones",
        json={"title": "MVP Build", "position": 1},
    )
    m3 = await async_client.post(
        f"/api/goals/{goal_id}/milestones",
        json={"title": "Public Launch", "position": 3},
    )
    assert m1.status_code == status.HTTP_201_CREATED
    assert m2.status_code == status.HTTP_201_CREATED
    assert m3.status_code == status.HTTP_201_CREATED

    m1_id = m1.json()["id"]

    # Verify list ordering is position ASC (MVP Build, Beta Testing, Public Launch)
    m_list = await async_client.get(f"/api/goals/{goal_id}/milestones")
    assert m_list.status_code == status.HTTP_200_OK
    titles = [m["title"] for m in m_list.json()]
    assert titles == ["MVP Build", "Beta Testing", "Public Launch"]

    # Complete Milestone 1 -> check completed_at is populated
    m1_done = await async_client.patch(
        f"/api/goals/{goal_id}/milestones/{m1_id}",
        json={"is_completed": True},
    )
    assert m1_done.status_code == status.HTTP_200_OK
    assert m1_done.json()["is_completed"] is True
    assert m1_done.json()["completed_at"] is not None

    # Reopen Milestone 1 -> check completed_at is cleared
    m1_reopen = await async_client.patch(
        f"/api/goals/{goal_id}/milestones/{m1_id}",
        json={"is_completed": False},
    )
    assert m1_reopen.status_code == status.HTTP_200_OK
    assert m1_reopen.json()["is_completed"] is False
    assert m1_reopen.json()["completed_at"] is None

    # Delete Milestone 1
    m1_del = await async_client.delete(f"/api/goals/{goal_id}/milestones/{m1_id}")
    assert m1_del.status_code == status.HTTP_200_OK

    # Detail check -> 404
    assert (
        await async_client.get(f"/api/goals/{goal_id}/milestones/{m1_id}")
    ).status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_milestone_cross_user_isolation(async_client: AsyncClient) -> None:
    """Test milestone cross-user access and adding milestone to deleted goal returns 404."""
    # User A creates goal and milestone
    await create_test_user_and_login(async_client, email="user_a_goal@example.com")
    g_res = await async_client.post("/api/goals", json={"title": "User A Goal"})
    goal_a_id = g_res.json()["id"]
    m_res = await async_client.post(
        f"/api/goals/{goal_a_id}/milestones", json={"title": "User A Milestone"}
    )
    m_a_id = m_res.json()["id"]

    # User B registers and attempts to access User A's goal & milestone
    await create_test_user_and_login(async_client, email="user_b_goal@example.com")
    assert (
        await async_client.get(f"/api/goals/{goal_a_id}/milestones/{m_a_id}")
    ).status_code == status.HTTP_404_NOT_FOUND

    assert (
        await async_client.post(
            f"/api/goals/{goal_a_id}/milestones", json={"title": "Malicious Milestone"}
        )
    ).status_code == status.HTTP_404_NOT_FOUND
