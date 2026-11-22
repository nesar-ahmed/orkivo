"""What the tasks module offers modules that report on work.

The ``insights`` module draws a workspace's and a person's dashboards; it does not
own the tasks they count (architecture doc section 5). These functions are the
tasks module's public answer to "how much work is where, and in what state?", so
no other module reads the tasks table to find out --- the same arrangement as
``project_links`` and ``label_links``.

They authorize nobody: the caller must already hold read access to the workspace,
or pass only tenants the access policy returned (``TaskService.my_scope``). Every
count comes from one grouped query per breakdown, whatever the size of the tenant.
"""

import uuid
from collections.abc import Collection, Mapping
from dataclasses import dataclass, fields
from datetime import date
from typing import Any

from sqlalchemy.orm import InstrumentedAttribute, Session

from app.modules.tasks import repository
from app.modules.tasks.enums import TaskPriority
from app.modules.tasks.models import Task


@dataclass(frozen=True)
class TaskCounts:
    """How much work a group holds, by status and by when it is due.

    The due-date counts cover only work that is not done, on the viewer's
    ``today``: ``overdue`` before it, ``due_today`` on it, ``due_next_7_days`` in
    the seven days after it --- the same buckets a person's own list uses.
    """

    total: int = 0
    todo: int = 0
    in_progress: int = 0
    done: int = 0
    overdue: int = 0
    due_today: int = 0
    due_next_7_days: int = 0

    @property
    def open(self) -> int:
        """Everything not done yet."""
        return self.todo + self.in_progress

    def __add__(self, other: "TaskCounts") -> "TaskCounts":
        return TaskCounts(
            **{
                field.name: getattr(self, field.name) + getattr(other, field.name)
                for field in fields(self)
            }
        )


NO_TASKS = TaskCounts()


@dataclass(frozen=True)
class Breakdown:
    """Counts per group, and open work per priority, for one dashboard."""

    groups: Mapping[uuid.UUID | None, TaskCounts]
    open_by_priority: Mapping[TaskPriority, int]

    @property
    def totals(self) -> TaskCounts:
        return sum(self.groups.values(), NO_TASKS)


def workspace_breakdown(session: Session, workspace_id: uuid.UUID, *, today: date) -> Breakdown:
    """One tenant's tasks per assignee (``None`` for unassigned) and per priority."""
    by_assignee = repository.count_in_workspace(
        session, workspace_id, by=Task.assignee_id, today=today
    )
    by_priority = repository.count_in_workspace(
        session, workspace_id, by=Task.priority, today=today
    )
    return _breakdown(by_assignee, by_priority)


def personal_breakdown(
    session: Session,
    *,
    user_id: uuid.UUID,
    workspace_ids: Collection[uuid.UUID],
    personal_workspace_id: uuid.UUID | None,
    today: date,
) -> Breakdown:
    """A person's own work per workspace and per priority.

    "Their own work" is what ``/me/tasks`` lists: assigned to them anywhere, plus
    their private workspace's unassigned tasks.
    """

    def count(by: InstrumentedAttribute[Any]) -> Mapping[Any, repository.CountRow]:
        return repository.count_assigned(
            session,
            user_id=user_id,
            workspace_ids=workspace_ids,
            personal_workspace_id=personal_workspace_id,
            by=by,
            today=today,
        )

    by_workspace = count(Task.workspace_id)
    by_priority = count(Task.priority)
    return _breakdown(by_workspace, by_priority)


def _breakdown(
    groups: Mapping[uuid.UUID | None, repository.CountRow],
    priorities: Mapping[TaskPriority, repository.CountRow],
) -> Breakdown:
    return Breakdown(
        groups={key: TaskCounts(*row) for key, row in groups.items()},
        open_by_priority={
            priority: TaskCounts(*priorities[priority]).open if priority in priorities else 0
            for priority in TaskPriority
        },
    )
