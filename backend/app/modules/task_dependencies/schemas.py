"""Pydantic request/response contracts for the task dependencies module.

SQLAlchemy models are never exposed directly as API responses
(architecture doc section 4.2).
"""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.tasks.enums import TaskAction, TaskPriority, TaskStatus
from app.modules.tasks.schemas import TaskPerson


class DependencyCreate(BaseModel):
    """Make the task wait on another task of the same workspace."""

    blocking_task_id: UUID


class DependencyTask(BaseModel):
    """A task on either side of a dependency: enough to judge it at a glance."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    status: TaskStatus
    priority: TaskPriority
    due_date: date | None
    # ``None`` while nobody is assigned.
    assignee: TaskPerson | None
    # What the caller may do to *this* task, as on ``TaskRead``: a link is removed
    # by whoever may change the task that waits, so a client needs it for both
    # sides. Filled in by the routes; empty --- read only --- by default.
    capabilities: list[TaskAction] = Field(default_factory=list)


class TaskDependenciesRead(BaseModel):
    """Both directions of one task's dependencies, open work first.

    ``blocked_by`` is what the task waits on; ``blocking`` is what waits on it.
    """

    blocked_by: list[DependencyTask]
    blocking: list[DependencyTask]
