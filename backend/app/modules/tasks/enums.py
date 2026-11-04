"""Enumerations for the tasks domain.

Values are stored as lowercase strings and are part of the public API
contract. Do not rename existing values; document how they evolve
(architecture doc section 6).
"""

from enum import StrEnum


class TaskStatus(StrEnum):
    """Kanban board statuses."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
