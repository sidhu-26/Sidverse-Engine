"""SQLAlchemy models registry and exports."""

from app.core.database import Base
from app.models.activity import Activity
from app.models.base import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin, utc_now
from app.models.duty import Duty
from app.models.enums import (
    ActivityAction,
    DutyPriority,
    GoalStatus,
    NotificationType,
    ProjectPriority,
    ProjectStatus,
    RecurrenceFrequency,
    ReminderStatus,
    ScheduleStatus,
    TaskPriority,
    TaskStatus,
)
from app.models.goal import Goal, GoalMilestone
from app.models.notification import Notification
from app.models.project import Project
from app.models.recurrence import RecurrenceRule
from app.models.reminder import Reminder
from app.models.review import DailyReview, WeeklyReview
from app.models.schedule import Schedule
from app.models.session import UserSession
from app.models.task import Task
from app.models.user import User

__all__ = [
    "Base",
    "UUIDPrimaryKeyMixin",
    "TimestampMixin",
    "SoftDeleteMixin",
    "utc_now",
    # Enums
    "ProjectStatus",
    "ProjectPriority",
    "TaskStatus",
    "TaskPriority",
    "GoalStatus",
    "DutyPriority",
    "RecurrenceFrequency",
    "ScheduleStatus",
    "ReminderStatus",
    "NotificationType",
    "ActivityAction",
    # Models
    "User",
    "UserSession",
    "Project",
    "Task",
    "Goal",
    "GoalMilestone",
    "Duty",
    "RecurrenceRule",
    "Schedule",
    "Reminder",
    "Notification",
    "Activity",
    "DailyReview",
    "WeeklyReview",
]
