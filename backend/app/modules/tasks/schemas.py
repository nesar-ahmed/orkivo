"""Pydantic request/response contracts for the tasks module.

SQLAlchemy models are never exposed directly as API responses
(architecture doc section 4.2).
"""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.labels.enums import LabelColor
from app.modules.tasks.enums import TaskAction, TaskPriority, TaskStatus

#: The range a due date may fall in. Wide enough for any real plan, narrow
#: enough that a typo such as year 0001 or 9999 is caught at the door.
MIN_DUE_DATE = date(1970, 1, 1)
MAX_DUE_DATE = date(2100, 12, 31)

#: How many labels one task may carry. Enough for any real taxonomy, few enough
#: that a row or a card can still show them.
MAX_LABELS_PER_TASK = 20

#: How many tasks one bulk request may change or delete: a full page of the
#: widest list, so "select all on this page" always fits in one request.
MAX_BULK_TASKS = 100


def _due_date_in_range(value: date) -> date:
    if not MIN_DUE_DATE <= value <= MAX_DUE_DATE:
        raise ValueError(
            f"Due date must be between {MIN_DUE_DATE.isoformat()} and {MAX_DUE_DATE.isoformat()}."
        )
    return value


def _unique_in_order(values: list[UUID]) -> list[UUID]:
    """A set of labels, sent as a list: repeats are dropped, the first one kept."""
    return list(dict.fromkeys(values))


TaskTitle = Annotated[str, Field(min_length=1, max_length=200)]
TaskDescription = Annotated[str | None, Field(default=None, max_length=5000)]
DueDate = Annotated[date, AfterValidator(_due_date_in_range)]
LabelIds = Annotated[
    list[UUID], Field(max_length=MAX_LABELS_PER_TASK), AfterValidator(_unique_in_order)
]


class TaskCreate(BaseModel):
    """Input contract for creating a task."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: TaskTitle
    description: TaskDescription = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: DueDate | None = None
    # Must be a member of the workspace the task is created in.
    assignee_id: UUID | None = None
    # Must be a project of the workspace the task is created in.
    project_id: UUID | None = None
    # Each must be a label of the workspace the task is created in.
    label_ids: LabelIds = Field(default_factory=list)


class TaskUpdate(BaseModel):
    """Partial update contract; only supplied fields are changed.

    ``description``, ``due_date``, ``assignee_id`` and ``project_id`` may be
    cleared with ``null``. ``title``, ``status`` and ``priority`` always have a
    value, so an explicit ``null`` is a validation error rather than a write the
    database would refuse.

    ``label_ids`` *replaces* the task's labels with exactly these; send ``[]`` to
    remove them all. ``null`` is a validation error rather than a second way to
    say "none".

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
    assignee_id: UUID | None = None
    project_id: UUID | None = None
    label_ids: LabelIds | None = None
    version: Annotated[int | None, Field(default=None, ge=1)] = None

    @field_validator("title", "status", "priority")
    @classmethod
    def _required_fields_cannot_be_cleared(cls, value: object) -> object:
        # Runs only when the field was supplied, so omitting it stays fine.
        if value is None:
            raise ValueError("This field cannot be empty.")
        return value

    @field_validator("label_ids")
    @classmethod
    def _labels_are_cleared_with_an_empty_list(cls, value: object) -> object:
        if value is None:
            raise ValueError("Send an empty list to remove every label.")
        return value


class BulkTaskRef(BaseModel):
    """One task in a bulk request, with the version the client last read.

    As on a single save, a supplied ``version`` that is stale refuses the whole
    request with ``409 TASK_CONFLICT``; omitting it keeps last-write-wins.
    """

    id: UUID
    version: Annotated[int | None, Field(default=None, ge=1)] = None


def _each_task_once(refs: list[BulkTaskRef]) -> list[BulkTaskRef]:
    """A task named twice is a malformed request, not "apply it twice"."""
    if len({ref.id for ref in refs}) != len(refs):
        raise ValueError("Each task may appear only once.")
    return refs


BulkTaskRefs = Annotated[
    list[BulkTaskRef],
    Field(min_length=1, max_length=MAX_BULK_TASKS),
    AfterValidator(_each_task_once),
]


class BulkTaskChanges(BaseModel):
    """What to change on every selected task; only supplied fields change.

    The fields a list's selection bar offers. ``due_date``, ``assignee_id`` and
    ``project_id`` may be cleared with ``null``; ``status`` and ``priority``
    cannot. Labels are *added* and *removed* rather than replaced, because the
    selected tasks carry different sets and "tag these as Bug" must not take
    anything else off them. A label may not be both added and removed.
    """

    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: DueDate | None = None
    assignee_id: UUID | None = None
    project_id: UUID | None = None
    add_label_ids: LabelIds = Field(default_factory=list)
    remove_label_ids: LabelIds = Field(default_factory=list)

    @field_validator("status", "priority")
    @classmethod
    def _required_fields_cannot_be_cleared(cls, value: object) -> object:
        if value is None:
            raise ValueError("This field cannot be empty.")
        return value

    @model_validator(mode="after")
    def _changes_something(self) -> "BulkTaskChanges":
        if not self.model_fields_set:
            raise ValueError("Name at least one change.")
        if set(self.add_label_ids) & set(self.remove_label_ids):
            raise ValueError("A label cannot be added and removed at once.")
        return self


class BulkTaskUpdate(BaseModel):
    """Apply one set of changes to several tasks of one workspace, all or nothing."""

    tasks: BulkTaskRefs
    changes: BulkTaskChanges


class BulkTaskDelete(BaseModel):
    """Delete several tasks of one workspace, all or nothing."""

    tasks: BulkTaskRefs


class TaskPerson(BaseModel):
    """Who created, changed or holds a task: enough to recognise, never an email."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str


class TaskProject(BaseModel):
    """The project a task is filed under: enough to label and group it."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class TaskLabel(BaseModel):
    """A label a task carries: enough to show it as a colored chip and filter by it."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    color: LabelColor


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
    # ``None`` while nobody is assigned.
    assignee: TaskPerson | None
    # ``None`` while the task is not filed under a project.
    project: TaskProject | None
    # Alphabetical; empty while the task carries no label.
    labels: list[TaskLabel]
    # How many unfinished tasks this one still waits on (``task_dependencies``).
    # Informative only: a blocked task can still be started or finished. Filled
    # in by the routes from one grouped query per response.
    open_blocker_count: int = 0
    # What the caller may do to this task right now (``tasks.permissions``): a
    # rendering hint like a workspace's ``capabilities``; every request is still
    # re-checked. Filled in by the routes; empty --- the safe default --- means
    # read only.
    capabilities: list[TaskAction] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class BulkTaskUpdateResponse(BaseModel):
    """Every task a bulk update changed, as it is now, in the order requested."""

    items: list[TaskRead]


class TaskListResponse(BaseModel):
    """Paginated collection envelope (architecture doc section 6/7)."""

    items: list[TaskRead]
    total: int
    page: int
    page_size: int
    pages: int
