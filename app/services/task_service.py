import math
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.enums import ActivityAction, TaskPriority, TaskStatus
from app.models.task import Task
from app.repositories.activity_repository import ActivityRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse, TaskUpdate

# Allowed task status transitions
ALLOWED_STATUS_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.TODO: {TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED, TaskStatus.CANCELLED},
    TaskStatus.IN_PROGRESS: {TaskStatus.TODO, TaskStatus.COMPLETED, TaskStatus.CANCELLED},
    TaskStatus.COMPLETED: {TaskStatus.TODO, TaskStatus.IN_PROGRESS},
    TaskStatus.CANCELLED: {TaskStatus.TODO},
}


class TaskService:
    """Core Task Engine business service."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.task_repo = TaskRepository(db)
        self.project_repo = ProjectRepository(db)
        self.activity_repo = ActivityRepository(db)

    async def create_task(self, user_id: uuid.UUID, data: TaskCreate) -> TaskResponse:
        """Create and persist a new task with project validation and activity logging."""
        # 1. Project Validation
        if data.project_id is not None:
            project = await self.project_repo.get_by_id_and_user(data.project_id, user_id)
            if not project:
                raise AppException(
                    message="The specified project does not exist or has been deleted.",
                    code="INVALID_PROJECT",
                    status_code=400,
                )

        # 2. Construct Entity
        task = Task(
            user_id=user_id,
            project_id=data.project_id,
            title=data.title,
            description=data.description,
            status=TaskStatus.TODO,
            priority=data.priority,
            due_at=data.due_at,
            estimated_minutes=data.estimated_minutes,
            completed_at=None,
        )

        created_task = await self.task_repo.create(task)

        # 3. Log Audit Activity
        await self.activity_repo.log_activity(
            user_id=user_id,
            entity_type="TASK",
            entity_id=created_task.id,
            action=ActivityAction.TASK_CREATED,
            metadata={
                "title": created_task.title,
                "priority": created_task.priority.value,
                "status": created_task.status.value,
                "project_id": str(created_task.project_id) if created_task.project_id else None,
            },
        )

        return self._to_response(created_task)

    async def get_task(self, task_id: uuid.UUID, user_id: uuid.UUID) -> TaskResponse:
        """Retrieve task detail for authenticated user."""
        task = await self.task_repo.get_by_id_and_user(task_id, user_id)
        if not task:
            raise AppException(
                message="Task not found.",
                code="TASK_NOT_FOUND",
                status_code=404,
            )
        return self._to_response(task)

    async def list_tasks(
        self,
        user_id: uuid.UUID,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        project_id: uuid.UUID | None = None,
        overdue: bool | None = None,
        due_before: datetime | None = None,
        due_after: datetime | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> TaskListResponse:
        """List authenticated user's tasks with filtering and pagination."""
        items, total = await self.task_repo.list_tasks(
            user_id=user_id,
            status=status,
            priority=priority,
            project_id=project_id,
            overdue=overdue,
            due_before=due_before,
            due_after=due_after,
            search=search,
            page=page,
            page_size=page_size,
        )

        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return TaskListResponse(
            items=[self._to_response(t) for t in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def update_task(
        self,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        data: TaskUpdate,
    ) -> TaskResponse:
        """Partially update task with status transitions, invariants, and audit logging."""
        task = await self.task_repo.get_by_id_and_user(task_id, user_id)
        if not task:
            raise AppException(
                message="Task not found.",
                code="TASK_NOT_FOUND",
                status_code=404,
            )

        changes: dict[str, dict[str, str | None]] = {}
        old_status = task.status
        old_due_at = task.due_at

        # 1. Project Validation
        if data.project_id is not None and data.project_id != task.project_id:
            project = await self.project_repo.get_by_id_and_user(data.project_id, user_id)
            if not project:
                raise AppException(
                    message="The specified project does not exist or has been deleted.",
                    code="INVALID_PROJECT",
                    status_code=400,
                )
            changes["project_id"] = {
                "old": str(task.project_id) if task.project_id else None,
                "new": str(data.project_id),
            }
            task.project_id = data.project_id

        # 2. Simple Field Updates
        if data.title is not None and data.title != task.title:
            changes["title"] = {"old": task.title, "new": data.title}
            task.title = data.title

        if data.description is not None and data.description != task.description:
            changes["description"] = {"old": task.description, "new": data.description}
            task.description = data.description

        if data.priority is not None and data.priority != task.priority:
            changes["priority"] = {"old": task.priority.value, "new": data.priority.value}
            task.priority = data.priority

        if data.estimated_minutes is not None and data.estimated_minutes != task.estimated_minutes:
            changes["estimated_minutes"] = {
                "old": str(task.estimated_minutes) if task.estimated_minutes else None,
                "new": str(data.estimated_minutes),
            }
            task.estimated_minutes = data.estimated_minutes

        # 3. Due Date / Rescheduling
        if data.due_at is not None and data.due_at != task.due_at:
            task.due_at = data.due_at
            await self.activity_repo.log_activity(
                user_id=user_id,
                entity_type="TASK",
                entity_id=task.id,
                action=ActivityAction.TASK_RESCHEDULED,
                metadata={
                    "old_due_at": old_due_at.isoformat() if old_due_at else None,
                    "new_due_at": data.due_at.isoformat(),
                },
            )

        # 4. Status Transition & Completion Invariant
        if data.status is not None and data.status != old_status:
            allowed = ALLOWED_STATUS_TRANSITIONS.get(old_status, set())
            if data.status not in allowed:
                raise AppException(
                    message=(
                        f"Cannot transition task status from '{old_status.value}' "
                        f"to '{data.status.value}'."
                    ),
                    code="INVALID_STATUS_TRANSITION",
                    status_code=400,
                )

            task.status = data.status

            if data.status == TaskStatus.COMPLETED:
                task.completed_at = datetime.now(UTC)
                await self.activity_repo.log_activity(
                    user_id=user_id,
                    entity_type="TASK",
                    entity_id=task.id,
                    action=ActivityAction.TASK_COMPLETED,
                    metadata={
                        "old_status": old_status.value,
                        "new_status": data.status.value,
                        "completed_at": task.completed_at.isoformat(),
                    },
                )
            elif old_status == TaskStatus.COMPLETED and data.status in (
                TaskStatus.TODO,
                TaskStatus.IN_PROGRESS,
            ):
                task.completed_at = None
                await self.activity_repo.log_activity(
                    user_id=user_id,
                    entity_type="TASK",
                    entity_id=task.id,
                    action=ActivityAction.TASK_REOPENED,
                    metadata={
                        "old_status": old_status.value,
                        "new_status": data.status.value,
                    },
                )
            elif data.status == TaskStatus.CANCELLED:
                task.completed_at = None
                await self.activity_repo.log_activity(
                    user_id=user_id,
                    entity_type="TASK",
                    entity_id=task.id,
                    action=ActivityAction.TASK_CANCELLED,
                    metadata={
                        "old_status": old_status.value,
                        "new_status": data.status.value,
                    },
                )
            else:
                changes["status"] = {"old": old_status.value, "new": data.status.value}

        # 5. General Updates Activity Log
        if changes:
            await self.activity_repo.log_activity(
                user_id=user_id,
                entity_type="TASK",
                entity_id=task.id,
                action=ActivityAction.TASK_UPDATED,
                metadata={"changes": changes},
            )

        updated_task = await self.task_repo.update(task)
        return self._to_response(updated_task)

    async def delete_task(self, task_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Soft delete task and record audit activity."""
        task = await self.task_repo.get_by_id_and_user(task_id, user_id)
        if not task:
            raise AppException(
                message="Task not found.",
                code="TASK_NOT_FOUND",
                status_code=404,
            )

        await self.task_repo.soft_delete(task)

        await self.activity_repo.log_activity(
            user_id=user_id,
            entity_type="TASK",
            entity_id=task.id,
            action=ActivityAction.TASK_DELETED,
            metadata={"title": task.title, "deleted_at": datetime.now(UTC).isoformat()},
        )

    def _to_response(self, task: Task) -> TaskResponse:
        """Convert Task ORM entity to TaskResponse with computed overdue status."""
        now = datetime.now(UTC)
        due_at_aware = task.due_at
        if due_at_aware is not None and due_at_aware.tzinfo is None:
            due_at_aware = due_at_aware.replace(tzinfo=UTC)

        is_overdue = bool(
            due_at_aware is not None
            and due_at_aware < now
            and task.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED)
            and task.deleted_at is None
        )

        return TaskResponse(
            id=task.id,
            user_id=task.user_id,
            project_id=task.project_id,
            title=task.title,
            description=task.description,
            status=task.status,
            priority=task.priority,
            due_at=task.due_at,
            estimated_minutes=task.estimated_minutes,
            completed_at=task.completed_at,
            is_overdue=is_overdue,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
