"""Pydantic request/response contracts for the tasks module.

SQLAlchemy models are never exposed directly as API responses
(architecture doc section 4.2).
"""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.tasks.enums import TaskPriority, TaskStatus

TaskTitle = Annotated[str, Field(min_length=1, max_length=200)]
TaskDescription = Annotated[str | None, Field(default=None, max_length=5000)]


class TaskCreate(BaseModel):
    """Input contract for creating a task."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: TaskTitle
    description: TaskDescription = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: date | None = None


class TaskUpdate(BaseModel):
    """Partial update contract; only supplied fields are changed."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: TaskTitle | None = None
    description: TaskDescription = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: date | None = None


class TaskRead(BaseModel):
    """Public representation of a task."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_date: date | None
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    """Paginated collection envelope (architecture doc section 6/7)."""

    items: list[TaskRead]
    total: int
    page: int
    page_size: int
    pages: int
