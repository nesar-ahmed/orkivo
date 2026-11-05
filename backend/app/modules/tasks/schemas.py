"""Pydantic request/response contracts for the tasks module.

SQLAlchemy models are never exposed directly as API responses
(architecture doc section 4.2).
"""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from app.modules.tasks.enums import TaskPriority, TaskStatus

#: The range a due date may fall in. Wide enough for any real plan, narrow
#: enough that a typo such as year 0001 or 9999 is caught at the door.
MIN_DUE_DATE = date(1970, 1, 1)
MAX_DUE_DATE = date(2100, 12, 31)


def _due_date_in_range(value: date) -> date:
    if not MIN_DUE_DATE <= value <= MAX_DUE_DATE:
        raise ValueError(
            f"Due date must be between {MIN_DUE_DATE.isoformat()} and {MAX_DUE_DATE.isoformat()}."
        )
    return value


TaskTitle = Annotated[str, Field(min_length=1, max_length=200)]
TaskDescription = Annotated[str | None, Field(default=None, max_length=5000)]
DueDate = Annotated[date, AfterValidator(_due_date_in_range)]


class TaskCreate(BaseModel):
    """Input contract for creating a task."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: TaskTitle
    description: TaskDescription = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: DueDate | None = None


class TaskUpdate(BaseModel):
    """Partial update contract; only supplied fields are changed.

    ``description`` and ``due_date`` may be cleared with ``null``. ``title``,
    ``status`` and ``priority`` always have a value, so an explicit ``null`` is
    a validation error rather than a write the database would refuse.

    ``version`` is the version the client last read. When supplied and stale,
    the update is refused with ``409 TASK_CONFLICT`` instead of overwriting a
    colleague's change. Omitting it keeps the old last-write-wins behaviour.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    title: TaskTitle | None = None
    description: TaskDescription = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: DueDate | None = None
    version: Annotated[int | None, Field(default=None, ge=1)] = None

    @field_validator("title", "status", "priority")
    @classmethod
    def _required_fields_cannot_be_cleared(cls, value: object) -> object:
        # Runs only when the field was supplied, so omitting it stays fine.
        if value is None:
            raise ValueError("This field cannot be empty.")
        return value


class TaskPerson(BaseModel):
    """Who created or last changed a task: enough to recognise, never an email."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str


class TaskRead(BaseModel):
    """Public representation of a task."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    # The tenant the task lives in. Lets a client link a task to its workspace;
    # who created it (``owner_id``) stays internal.
    workspace_id: UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_date: date | None
    # Increments on every change; send it back on update to detect conflicts.
    version: int
    # ``None`` only if the account is gone; ``updated_by`` is ``None`` until the
    # task is first edited.
    created_by: TaskPerson | None
    updated_by: TaskPerson | None
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    """Paginated collection envelope (architecture doc section 6/7)."""

    items: list[TaskRead]
    total: int
    page: int
    page_size: int
    pages: int
