import enum


class ProjectStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class ProjectPriority(enum.StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TaskStatus(enum.StrEnum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TaskPriority(enum.StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class GoalStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class DutyPriority(enum.StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class RecurrenceFrequency(enum.StrEnum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class ScheduleStatus(enum.StrEnum):
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ReminderStatus(enum.StrEnum):
    PENDING = "PENDING"
    TRIGGERED = "TRIGGERED"
    DISMISSED = "DISMISSED"
    CANCELLED = "CANCELLED"


class NotificationType(enum.StrEnum):
    REMINDER = "REMINDER"
    DEADLINE = "DEADLINE"
    DUTY = "DUTY"
    SYSTEM = "SYSTEM"


class ActivityAction(enum.StrEnum):
    TASK_CREATED = "TASK_CREATED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_RESCHEDULED = "TASK_RESCHEDULED"
    TASK_REOPENED = "TASK_REOPENED"
    DUTY_COMPLETED = "DUTY_COMPLETED"
    PROJECT_CREATED = "PROJECT_CREATED"
    GOAL_UPDATED = "GOAL_UPDATED"
    DEADLINE_CHANGED = "DEADLINE_CHANGED"
    SCHEDULE_CREATED = "SCHEDULE_CREATED"
    SCHEDULE_COMPLETED = "SCHEDULE_COMPLETED"
    REMINDER_TRIGGERED = "REMINDER_TRIGGERED"
