"""Database access for the tasks module.

The repository encapsulates queries only. It does not decide authorization
policy and does not return HTTP responses; transaction commits happen at the
service layer (architecture doc sections 4.1 and 6.2).

Who may read a tenant is decided by ``workspaces.access`` before any function
here runs. The list queries still carry the tenant predicate unconditionally, so
a page of tasks can only ever come from the workspace --- or, for a person's own
list, the set of workspaces --- that was authorized. Both lists share one filter
and one ordering function, so "open", "due this week" or "labelled Bug" mean the
same thing on a board and on a person's own list.

Sorting by project joins the ``projects`` table through ``Task.project``. That
reads the projects module's *model* for a join, as ``workspaces.repository`` does
with ``User``; it never calls the projects module's repository. The labels a task
carries are read the same way, through the ``task_labels`` table this module owns
and the labels module's ``Label`` model.
"""

import uuid
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, NamedTuple

from sqlalchemy import (
    ColumnElement,
    Select,
    and_,
    case,
    delete,
    exists,
    func,
    or_,
    select,
    update,
)
from sqlalchemy.orm import InstrumentedAttribute, Session, contains_eager

from app.modules.labels.models import Label
from app.modules.projects.models import Project
from app.modules.tasks.enums import TaskOrder, TaskPriority, TaskStatus
from app.modules.tasks.models import Task, task_labels
from app.shared.time import utc_now


@dataclass(frozen=True)
class TaskFilters:
    """What a list of tasks is narrowed by; the defaults narrow nothing.

    Pairs are exclusive, and the service never sets both halves: ``assignee_id``
    keeps one person's tasks and ``unassigned`` the tasks nobody holds;
    ``project_id`` / ``without_project`` and ``label_id`` / ``without_labels`` do
    the same for projects and labels, and ``status`` / ``open_only`` for one
    status or everything not done. ``due_from`` and ``due_to`` bound the due date,
    both inclusive (so a dateless task never falls inside a window), and
    ``has_due_date`` keeps only scheduled (``True``) or unscheduled (``False``)
    tasks.
    """

    status: TaskStatus | None = None
    open_only: bool = False
    priority: TaskPriority | None = None
    assignee_id: uuid.UUID | None = None
    unassigned: bool = False
    project_id: uuid.UUID | None = None
    without_project: bool = False
    label_id: uuid.UUID | None = None
    without_labels: bool = False
    due_from: date | None = None
    due_to: date | None = None
    has_due_date: bool | None = None
    search: str | None = None


#: Narrows nothing. Safe to share as a default: ``TaskFilters`` is frozen.
NO_FILTERS = TaskFilters()


def list_tasks(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    filters: TaskFilters = NO_FILTERS,
    order: TaskOrder = TaskOrder.NEWEST,
    page: int = 1,
    page_size: int = 20,
) -> tuple[Sequence[Task], int]:
    """Return one page of a tenant's tasks plus the total matching count."""
    # The tenant predicate is applied first and unconditionally: no query path
    # may return rows from another workspace (architecture doc section 9).
    stmt: Select[Task] = select(Task).where(Task.workspace_id == workspace_id)
    return _page(session, _ordered(_filtered(stmt, filters), order), page, page_size)


def list_assigned(
    session: Session,
    *,
    user_id: uuid.UUID,
    workspace_ids: Collection[uuid.UUID],
    personal_workspace_id: uuid.UUID | None,
    filters: TaskFilters = NO_FILTERS,
    order: TaskOrder = TaskOrder.DUE,
    page: int = 1,
    page_size: int = 20,
) -> tuple[Sequence[Task], int]:
    """One page of a person's own work across the tenants they may read.

    "Their own work" is every task assigned to them, plus the unassigned tasks
    of their private workspace --- which nobody else can hold, so those are
    theirs too. ``workspace_ids`` is the tenant predicate: the service passes
    only tenants the access policy says the caller may read, and this query
    never looks outside them.
    """
    if not workspace_ids:
        return [], 0
    mine = _mine(
        user_id=user_id, workspace_ids=workspace_ids, personal_workspace_id=personal_workspace_id
    )
    stmt: Select[Task] = select(Task).where(*mine)
    return _page(session, _ordered(_filtered(stmt, filters), order), page, page_size)


def _mine(
    *,
    user_id: uuid.UUID,
    workspace_ids: Collection[uuid.UUID],
    personal_workspace_id: uuid.UUID | None,
) -> tuple[ColumnElement[bool], ...]:
    """A person's own work, as criteria: one definition for their list and their counts.

    Assigned to them, plus their private workspace's unassigned tasks, inside the
    tenants in ``workspace_ids`` --- the tenant predicate, always present.
    """
    mine: ColumnElement[bool] = Task.assignee_id == user_id
    if personal_workspace_id is not None:
        mine = or_(
            mine,
            and_(Task.workspace_id == personal_workspace_id, Task.assignee_id.is_(None)),
        )
    return (Task.workspace_id.in_(list(workspace_ids)), mine)


def _filtered(stmt: Select[Task], filters: TaskFilters) -> Select[Task]:
    if filters.status is not None:
        stmt = stmt.where(Task.status == filters.status)
    elif filters.open_only:
        stmt = stmt.where(Task.status != TaskStatus.DONE)
    if filters.priority is not None:
        stmt = stmt.where(Task.priority == filters.priority)
    if filters.assignee_id is not None:
        stmt = stmt.where(Task.assignee_id == filters.assignee_id)
    elif filters.unassigned:
        stmt = stmt.where(Task.assignee_id.is_(None))
    if filters.project_id is not None:
        stmt = stmt.where(Task.project_id == filters.project_id)
    elif filters.without_project:
        stmt = stmt.where(Task.project_id.is_(None))
    if filters.label_id is not None:
        # A semi-join rather than a join: a task is listed once, whatever it carries.
        stmt = stmt.where(
            Task.id.in_(
                select(task_labels.c.task_id).where(task_labels.c.label_id == filters.label_id)
            )
        )
    elif filters.without_labels:
        stmt = stmt.where(~exists().where(task_labels.c.task_id == Task.id))
    if filters.due_from is not None:
        stmt = stmt.where(Task.due_date >= filters.due_from)
    if filters.due_to is not None:
        stmt = stmt.where(Task.due_date <= filters.due_to)
    if filters.has_due_date is True:
        stmt = stmt.where(Task.due_date.is_not(None))
    elif filters.has_due_date is False:
        stmt = stmt.where(Task.due_date.is_(None))
    if filters.search:
        stmt = stmt.where(
            or_(
                # icontains escapes LIKE wildcards (% and _) in user input.
                Task.title.icontains(filters.search, autoescape=True),
                Task.description.icontains(filters.search, autoescape=True),
            )
        )
    return stmt


#: High before medium before low. Stored values are strings, so their
#: alphabetical order ("high", "low", "medium") would be wrong.
_PRIORITY_RANK = case(
    (Task.priority == TaskPriority.HIGH, 0),
    (Task.priority == TaskPriority.MEDIUM, 1),
    else_=2,
)


def _ordered(stmt: Select[Task], order: TaskOrder) -> Select[Task]:
    """Sort for ``order``; every order ends newest first, then by id, so pages are stable."""
    if order is TaskOrder.PROJECT:
        # The join that sorts by project name also loads ``task.project``, so
        # the projects table is joined once rather than twice.
        stmt = (
            stmt.outerjoin(Task.project)
            .options(contains_eager(Task.project))
            .order_by(
                # Tasks without a project last, then projects alphabetically.
                Task.project_id.is_(None),
                Project.name_key,
                Project.id,
            )
        )
    elif order is TaskOrder.DUE:
        # Undated last: spelled as a boolean key, since the databases disagree
        # about where NULL sorts by default.
        stmt = stmt.order_by(Task.due_date.is_(None), Task.due_date, _PRIORITY_RANK)
    elif order is TaskOrder.PRIORITY:
        stmt = stmt.order_by(_PRIORITY_RANK, Task.due_date.is_(None), Task.due_date)
    return stmt.order_by(Task.created_at.desc(), Task.id.desc())


def _page(
    session: Session, stmt: Select[Task], page: int, page_size: int
) -> tuple[Sequence[Task], int]:
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = session.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return items, total


def get_task(session: Session, task_id: uuid.UUID) -> Task | None:
    """Fetch a task by id, *before* authorization.

    Deliberately unscoped: which workspace holds the task is exactly what the
    service needs to know in order to ask the access policy. The service never
    returns this row, or anything derived from it, until that check has passed.
    """
    return session.get(Task, task_id)


def get_tasks_in_workspace(
    session: Session, workspace_id: uuid.UUID, task_ids: Collection[uuid.UUID]
) -> Mapping[uuid.UUID, Task]:
    """The tasks among ``task_ids`` that live in ``workspace_id``, by id, in one query.

    For a bulk request on one workspace: the tenant predicate is part of the
    query, so an id from another workspace is simply absent --- exactly like an id
    that does not exist.
    """
    if not task_ids:
        return {}
    tasks = session.scalars(
        select(Task).where(Task.workspace_id == workspace_id, Task.id.in_(list(task_ids)))
    ).all()
    return {task.id: task for task in tasks}


def find_by_title(
    session: Session, *, workspace_ids: Collection[uuid.UUID], term: str, limit: int
) -> Sequence[Task]:
    """Tasks whose title contains ``term``, best matches first, in these tenants only.

    A title that starts with the term beats one with a word that does, which beats
    one that merely contains it; open work beats finished work; then the most
    recently changed. ``icontains`` escapes LIKE wildcards in what was typed.
    """
    if not workspace_ids:
        return []
    rank = case(
        (Task.title.istartswith(term, autoescape=True), 0),
        (Task.title.icontains(f" {term}", autoescape=True), 1),
        else_=2,
    )
    return session.scalars(
        select(Task)
        .where(
            Task.workspace_id.in_(list(workspace_ids)),
            Task.title.icontains(term, autoescape=True),
        )
        .order_by(rank, Task.status == TaskStatus.DONE, Task.updated_at.desc(), Task.id)
        .limit(limit)
    ).all()


def add_task(session: Session, task: Task) -> None:
    session.add(task)
    session.flush()


def delete_task(session: Session, task: Task) -> None:
    session.delete(task)


class BulkEdited(NamedTuple):
    """A task changed by a bulk edit, as it is *after* the change."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    version: int


def unassign_member(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> Sequence[BulkEdited]:
    """Clear one account's assignments inside one tenant; return the tasks changed."""
    return _edit_in_bulk(
        session,
        (Task.workspace_id == workspace_id, Task.assignee_id == user_id),
        {"assignee_id": None},
        actor_id=actor_id,
    )


def detach_project(
    session: Session, *, project_id: uuid.UUID, actor_id: uuid.UUID
) -> Sequence[BulkEdited]:
    """Take every task out of a project that is about to go; return the tasks changed."""
    return _edit_in_bulk(
        session, (Task.project_id == project_id,), {"project_id": None}, actor_id=actor_id
    )


def count_by_project(
    session: Session, project_ids: Collection[uuid.UUID]
) -> Mapping[uuid.UUID, tuple[int, int]]:
    """``(all tasks, open tasks)`` per project, in one grouped query.

    "Open" is anything not done. Projects holding no tasks are simply absent.
    """
    if not project_ids:
        return {}
    open_tasks = func.sum(case((Task.status != TaskStatus.DONE, 1), else_=0))
    rows = session.execute(
        select(Task.project_id, func.count(Task.id), open_tasks)
        .where(Task.project_id.in_(list(project_ids)))
        .group_by(Task.project_id)
    ).all()
    return {
        project_id: (int(total), int(still_open or 0))
        for project_id, total, still_open in rows
        if project_id is not None
    }


def count_by_label(
    session: Session, label_ids: Collection[uuid.UUID]
) -> Mapping[uuid.UUID, int]:
    """How many tasks carry each label, in one grouped query.

    Labels no task carries are simply absent.
    """
    if not label_ids:
        return {}
    rows = session.execute(
        select(task_labels.c.label_id, func.count())
        .where(task_labels.c.label_id.in_(list(label_ids)))
        .group_by(task_labels.c.label_id)
    ).all()
    return {label_id: int(count) for label_id, count in rows}


def labels_of_tasks_carrying(
    session: Session, label_id: uuid.UUID
) -> Mapping[uuid.UUID, Sequence[Label]]:
    """Every label of every task that carries ``label_id``, by task.

    What those tasks look like *before* the label is taken off them, read in one
    query so a label on hundreds of tasks is not a query per task.
    """
    carriers = select(task_labels.c.task_id).where(task_labels.c.label_id == label_id)
    rows = session.execute(
        select(task_labels.c.task_id, Label)
        .join(Label, Label.id == task_labels.c.label_id)
        .where(task_labels.c.task_id.in_(carriers))
        .order_by(task_labels.c.task_id, Label.name_key, Label.id)
    ).all()
    found: dict[uuid.UUID, list[Label]] = {}
    for task_id, label in rows:
        found.setdefault(task_id, []).append(label)
    return found


def remove_label(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    label_id: uuid.UUID,
    task_ids: Collection[uuid.UUID],
    actor_id: uuid.UUID,
) -> Sequence[BulkEdited]:
    """Take a label off these tasks of one tenant; return the tasks changed.

    The links go in one DELETE, and each task is recorded as edited (a new
    version, by ``actor_id``) in one UPDATE, so a colleague still holding the old
    version gets a conflict rather than writing the label back.
    """
    if not task_ids:
        return []
    session.execute(
        delete(task_labels).where(
            task_labels.c.label_id == label_id, task_labels.c.task_id.in_(list(task_ids))
        )
    )
    return _edit_in_bulk(
        session,
        (Task.workspace_id == workspace_id, Task.id.in_(list(task_ids))),
        {},
        actor_id=actor_id,
    )


def _edit_in_bulk(
    session: Session,
    criteria: tuple[ColumnElement[bool], ...],
    values: Mapping[str, Any],
    *,
    actor_id: uuid.UUID,
) -> Sequence[BulkEdited]:
    """Apply ``values`` to every matching task as one recorded edit per task.

    A single UPDATE rather than a load-and-loop, so releasing hundreds of tasks is
    one statement and no concurrent save can make it fail halfway. It bumps
    ``version`` and records the editor exactly as an ordinary save would, so a
    colleague who had one of these tasks open gets ``409 TASK_CONFLICT`` instead
    of silently writing the old value back. ``RETURNING`` hands back what the
    activity log needs about each task without reading them again.

    Tasks already loaded in this session are expired afterwards --- columns *and*
    the joined relationships --- so nothing later in the unit of work reads what
    was just cleared.
    """
    rows = session.execute(
        update(Task)
        .where(*criteria)
        .values(
            **values,
            version=Task.version + 1,
            updated_by_id=actor_id,
            updated_at=utc_now(),
        )
        .returning(Task.id, Task.workspace_id, Task.title, Task.version),
        execution_options={"synchronize_session": False},
    ).all()
    changed = [BulkEdited(*row) for row in rows]
    for task in changed:
        loaded = session.identity_map.get(Session.identity_key(Task, task.id))
        if loaded is not None:
            session.expire(loaded)
    return changed


# --- counts ------------------------------------------------------------------------
class CountRow(NamedTuple):
    """How many tasks one group holds, by status and by where their due date falls.

    The due-date columns count only work that is not done, on the day ``today``
    the caller passed: ``overdue`` is due before it, ``due_today`` on it, and
    ``due_next_7_days`` in the seven days after it --- the buckets a person's own
    list is grouped into.
    """

    total: int
    todo: int
    in_progress: int
    done: int
    overdue: int
    due_today: int
    due_next_7_days: int


def count_in_workspace(
    session: Session, workspace_id: uuid.UUID, *, by: InstrumentedAttribute[Any], today: date
) -> Mapping[Any, CountRow]:
    """One tenant's tasks counted per value of ``by`` (an assignee, a priority)."""
    return _grouped_counts(session, (Task.workspace_id == workspace_id,), by=by, today=today)


def count_assigned(
    session: Session,
    *,
    user_id: uuid.UUID,
    workspace_ids: Collection[uuid.UUID],
    personal_workspace_id: uuid.UUID | None,
    by: InstrumentedAttribute[Any],
    today: date,
) -> Mapping[Any, CountRow]:
    """A person's own work (as ``list_assigned`` reads it) counted per value of ``by``."""
    if not workspace_ids:
        return {}
    criteria = _mine(
        user_id=user_id, workspace_ids=workspace_ids, personal_workspace_id=personal_workspace_id
    )
    return _grouped_counts(session, criteria, by=by, today=today)


def _grouped_counts(
    session: Session,
    criteria: tuple[ColumnElement[bool], ...],
    *,
    by: InstrumentedAttribute[Any],
    today: date,
) -> Mapping[Any, CountRow]:
    """Every count a dashboard shows, per group, in one aggregate query.

    Conditional sums rather than one query per number, so a workspace of any size
    costs one round trip per breakdown. Groups holding no tasks are simply absent.
    """
    still_open = Task.status != TaskStatus.DONE

    def how_many(condition: ColumnElement[bool]) -> Any:
        return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)

    rows = session.execute(
        select(
            by,
            func.count(Task.id),
            how_many(Task.status == TaskStatus.TODO),
            how_many(Task.status == TaskStatus.IN_PROGRESS),
            how_many(Task.status == TaskStatus.DONE),
            how_many(and_(still_open, Task.due_date < today)),
            how_many(and_(still_open, Task.due_date == today)),
            how_many(
                and_(
                    still_open,
                    Task.due_date > today,
                    Task.due_date <= today + timedelta(days=7),
                )
            ),
        )
        .where(*criteria)
        .group_by(by)
    ).all()
    return {key: CountRow(*(int(value) for value in counts)) for key, *counts in rows}
