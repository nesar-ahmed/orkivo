"""Pydantic response contracts for the insights module.

SQLAlchemy models are never exposed directly as API responses (architecture doc
section 4.2). People are shown by name, never by email, as on a task.
"""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.workspaces.enums import WorkspaceKind, WorkspaceRole


class TaskCountsRead(BaseModel):
    """How much work a group holds.

    ``open`` is everything not done (``todo`` + ``in_progress``). The due-date
    counts cover open work only, on the ``today`` the response names: due before
    it, on it, and in the seven days after it.
    """

    model_config = ConfigDict(from_attributes=True)

    total: int
    todo: int
    in_progress: int
    done: int
    open: int
    overdue: int
    due_today: int
    due_next_7_days: int


class PriorityCountsRead(BaseModel):
    """Open work per priority."""

    high: int
    medium: int
    low: int


class InsightPerson(BaseModel):
    """Whose workload a row is: enough to recognise, never an email."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str


class MemberWorkloadRead(BaseModel):
    """One member's share of the work; ``person`` and ``role`` are ``None`` on the
    row for tasks nobody holds."""

    person: InsightPerson | None
    role: WorkspaceRole | None
    counts: TaskCountsRead


class WorkspaceStatsRead(BaseModel):
    """A workspace's dashboard: its counts, and how open work is spread.

    ``workload`` lists every member, busiest first, then the unassigned row.
    """

    workspace_id: UUID
    today: date
    totals: TaskCountsRead
    open_by_priority: PriorityCountsRead
    workload: list[MemberWorkloadRead]


class InsightWorkspace(BaseModel):
    """Where a share of someone's work lives: enough to name it and link to it."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    kind: WorkspaceKind
    slug: str | None


class WorkspaceWorkloadRead(BaseModel):
    workspace: InsightWorkspace
    counts: TaskCountsRead


class MyStatsRead(BaseModel):
    """A person's own dashboard: their work everywhere, counted, per workspace.

    The same tasks ``/me/tasks`` lists. ``by_workspace`` names every workspace
    they may read, private first, including those holding none of their work.
    """

    today: date
    totals: TaskCountsRead
    open_by_priority: PriorityCountsRead
    by_workspace: list[WorkspaceWorkloadRead]
