"""Pydantic schemas package."""

from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from app.schemas.goal import (
    GoalCreate,
    GoalListResponse,
    GoalMilestoneCreate,
    GoalMilestoneResponse,
    GoalMilestoneUpdate,
    GoalResponse,
    GoalUpdate,
)
from app.schemas.notification import (
    NotificationListResponse,
    NotificationResponse,
    NotificationUpdate,
)
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.schemas.reminder import (
    ReminderCreate,
    ReminderListResponse,
    ReminderResponse,
    ReminderUpdate,
)
from app.schemas.schedule import (
    ScheduleCreate,
    ScheduleListResponse,
    ScheduleResponse,
    ScheduleUpdate,
)
from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse, TaskUpdate
from app.schemas.user import UserResponse

__all__ = [
    "UserResponse",
    "RegisterRequest",
    "LoginRequest",
    "AuthResponse",
    "TaskCreate",
    "TaskUpdate",
    "TaskResponse",
    "TaskListResponse",
    "ScheduleCreate",
    "ScheduleUpdate",
    "ScheduleResponse",
    "ScheduleListResponse",
    "ReminderCreate",
    "ReminderUpdate",
    "ReminderResponse",
    "ReminderListResponse",
    "NotificationResponse",
    "NotificationUpdate",
    "NotificationListResponse",
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectResponse",
    "ProjectListResponse",
    "GoalCreate",
    "GoalUpdate",
    "GoalResponse",
    "GoalListResponse",
    "GoalMilestoneCreate",
    "GoalMilestoneUpdate",
    "GoalMilestoneResponse",
]
