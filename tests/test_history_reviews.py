from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import AsyncClient
from starlette import status

from tests.test_tasks import create_test_user_and_login


@pytest.mark.asyncio
async def test_history_list_filter_and_pagination(async_client: AsyncClient) -> None:
    """Test activity logging, filtering, pagination, and single item retrieval."""
    user = await create_test_user_and_login(async_client, email="hist_user@example.com")

    # 1. Generate multiple activity events via Task actions
    r_task = await async_client.post(
        "/api/tasks",
        json={"title": "History Tracking Task", "priority": "HIGH"},
    )
    assert r_task.status_code == status.HTTP_201_CREATED
    task_id = r_task.json()["id"]

    # Update task to trigger TASK_RESCHEDULED and TASK_COMPLETED
    new_due = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    await async_client.patch(f"/api/tasks/{task_id}", json={"due_at": new_due})
    await async_client.patch(f"/api/tasks/{task_id}", json={"status": "COMPLETED"})

    # 2. List all history for this user
    r_hist = await async_client.get("/api/history")
    assert r_hist.status_code == status.HTTP_200_OK
    hist_data = r_hist.json()
    assert hist_data["total"] >= 3
    actions = [item["action"] for item in hist_data["items"]]
    assert "TASK_CREATED" in actions
    assert "TASK_RESCHEDULED" in actions
    assert "TASK_COMPLETED" in actions

    # 3. Filter by entity_type
    r_filt_type = await async_client.get("/api/history?entity_type=TASK")
    assert r_filt_type.status_code == status.HTTP_200_OK
    assert all(item["entity_type"] == "TASK" for item in r_filt_type.json()["items"])

    # 4. Filter by action
    r_filt_action = await async_client.get("/api/history?action=TASK_COMPLETED")
    assert r_filt_action.status_code == status.HTTP_200_OK
    assert len(r_filt_action.json()["items"]) == 1
    assert r_filt_action.json()["items"][0]["action"] == "TASK_COMPLETED"
    completed_activity_id = r_filt_action.json()["items"][0]["id"]

    # 5. Get single activity item
    r_single = await async_client.get(f"/api/history/{completed_activity_id}")
    assert r_single.status_code == status.HTTP_200_OK
    assert r_single.json()["id"] == completed_activity_id
    assert r_single.json()["user_id"] == user["id"]

    # 6. Pagination
    r_page = await async_client.get("/api/history?page=1&page_size=2")
    assert r_page.status_code == status.HTTP_200_OK
    assert len(r_page.json()["items"]) == 2
    assert r_page.json()["page"] == 1
    assert r_page.json()["page_size"] == 2


@pytest.mark.asyncio
async def test_history_cross_user_isolation(async_client: AsyncClient) -> None:
    """Test that users cannot access or view another user's activity history."""
    await create_test_user_and_login(async_client, email="hist_user_a@example.com")
    r_task_a = await async_client.post("/api/tasks", json={"title": "User A Private Task"})
    task_a_id = r_task_a.json()["id"]

    r_hist_a = await async_client.get(f"/api/history?entity_id={task_a_id}")
    act_a_id = r_hist_a.json()["items"][0]["id"]

    # Switch to User B
    await create_test_user_and_login(async_client, email="hist_user_b@example.com")

    # User B listing history should NOT contain User A's activities
    r_hist_b = await async_client.get("/api/history")
    b_activity_ids = [item["id"] for item in r_hist_b.json()["items"]]
    assert act_a_id not in b_activity_ids

    # User B attempting direct GET on User A's activity receives 404
    r_idor = await async_client.get(f"/api/history/{act_a_id}")
    assert r_idor.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_daily_review_lifecycle_and_metrics(async_client: AsyncClient) -> None:
    """Test daily review lifecycle: creation, metrics, upsert, notes preservation, and listing."""
    user = await create_test_user_and_login(async_client, email="daily_rev_user@example.com")
    today = date.today()

    # Create tasks: 1 completed today, 1 overdue, 1 future incomplete
    r_t1 = await async_client.post("/api/tasks", json={"title": "Daily Task Completed Today"})
    t1_id = r_t1.json()["id"]
    await async_client.patch(f"/api/tasks/{t1_id}", json={"status": "COMPLETED"})

    yesterday_dt = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    await async_client.post(
        "/api/tasks",
        json={"title": "Overdue Daily Task", "due_at": yesterday_dt},
    )

    # 1. Create / Upsert Daily Review for today
    r_create = await async_client.post(
        "/api/reviews/daily",
        json={"review_date": today.isoformat(), "notes": "Great productive day."},
    )
    assert r_create.status_code == status.HTTP_200_OK
    rev = r_create.json()
    assert rev["review_date"] == today.isoformat()
    assert rev["completed_tasks"] >= 1
    assert rev["overdue_tasks"] >= 1
    assert rev["notes"] == "Great productive day."
    assert rev["user_id"] == user["id"]

    # 2. Duplicate submission performs upsert and updates metrics without error
    r_upsert = await async_client.post(
        "/api/reviews/daily",
        json={"review_date": today.isoformat(), "notes": "Updated reflection notes."},
    )
    assert r_upsert.status_code == status.HTTP_200_OK
    assert r_upsert.json()["id"] == rev["id"]
    assert r_upsert.json()["notes"] == "Updated reflection notes."

    # 3. Get Daily Review by date
    r_get = await async_client.get(f"/api/reviews/daily/{today.isoformat()}")
    assert r_get.status_code == status.HTTP_200_OK
    assert r_get.json()["id"] == rev["id"]

    # 4. Patch Daily Review (notes update only, preserving metrics)
    r_patch = await async_client.patch(
        f"/api/reviews/daily/{today.isoformat()}",
        json={"notes": "Final nightly note.", "recalculate": False},
    )
    assert r_patch.status_code == status.HTTP_200_OK
    assert r_patch.json()["notes"] == "Final nightly note."
    assert r_patch.json()["completed_tasks"] == rev["completed_tasks"]

    # 5. List Daily Reviews
    r_list = await async_client.get("/api/reviews/daily")
    assert r_list.status_code == status.HTTP_200_OK
    assert r_list.json()["total"] >= 1
    assert r_list.json()["items"][0]["review_date"] == today.isoformat()


@pytest.mark.asyncio
async def test_weekly_review_lifecycle_and_metrics(async_client: AsyncClient) -> None:
    """Test weekly review creation, Monday-Sunday normalization, metrics, upsert, and listing."""
    user = await create_test_user_and_login(async_client, email="weekly_rev_user@example.com")
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)

    # 1. Create / Upsert Weekly Review
    r_create = await async_client.post(
        "/api/reviews/weekly",
        json={"week_start": today.isoformat(), "notes": "Weekly sprint recap."},
    )
    assert r_create.status_code == status.HTTP_200_OK
    w_rev = r_create.json()
    assert w_rev["week_start"] == monday.isoformat()  # normalized to Monday
    assert w_rev["week_end"] == sunday.isoformat()  # ends Sunday
    assert w_rev["user_id"] == user["id"]
    assert w_rev["notes"] == "Weekly sprint recap."

    # 2. Get Weekly Review
    r_get = await async_client.get(f"/api/reviews/weekly/{monday.isoformat()}")
    assert r_get.status_code == status.HTTP_200_OK
    assert r_get.json()["id"] == w_rev["id"]

    # 3. Patch Weekly Review
    r_patch = await async_client.patch(
        f"/api/reviews/weekly/{monday.isoformat()}",
        json={"notes": "Adjusted weekly summary.", "recalculate": True},
    )
    assert r_patch.status_code == status.HTTP_200_OK
    assert r_patch.json()["notes"] == "Adjusted weekly summary."

    # 4. List Weekly Reviews
    r_list = await async_client.get("/api/reviews/weekly")
    assert r_list.status_code == status.HTTP_200_OK
    assert r_list.json()["total"] >= 1


@pytest.mark.asyncio
async def test_review_cross_user_isolation(async_client: AsyncClient) -> None:
    """Test that users cannot view or modify another user's reviews."""
    await create_test_user_and_login(async_client, email="rev_owner@example.com")
    target_date = date(2026, 5, 1)

    await async_client.post(
        "/api/reviews/daily",
        json={"review_date": target_date.isoformat(), "notes": "Owner private review"},
    )

    # Switch to intruder
    await create_test_user_and_login(async_client, email="rev_intruder@example.com")

    # Intruder GET receives 404
    r_get = await async_client.get(f"/api/reviews/daily/{target_date.isoformat()}")
    assert r_get.status_code == status.HTTP_404_NOT_FOUND

    # Intruder PATCH receives 404
    r_patch = await async_client.patch(
        f"/api/reviews/daily/{target_date.isoformat()}",
        json={"notes": "Intruder attempt"},
    )
    assert r_patch.status_code == status.HTTP_404_NOT_FOUND
