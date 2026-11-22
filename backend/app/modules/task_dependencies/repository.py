"""Database access for the task dependencies module.

The repository encapsulates queries only. It does not decide authorization
policy and does not return HTTP responses; transaction commits happen at the
service layer (architecture doc sections 4.1 and 6.2).

The task on the path has been authorized before any function here runs, and
every query still carries its workspace: a link, a blocking task or a step of a
cycle search can only ever be found inside the one tenant that was authorized.
Tasks are read through the tasks module's ``Task`` model, for joins only, as
``tasks.repository`` reads ``Project``.
"""

import uuid
from collections.abc import Collection, Mapping, Sequence

from sqlalchemy import Select, exists, func, select
from sqlalchemy.orm import Session, aliased

from app.modules.task_dependencies.models import TaskDependency
from app.modules.tasks.enums import TaskStatus
from app.modules.tasks.models import Task
from app.modules.workspaces.models import Workspace


def task_in_workspace(
    session: Session, workspace_id: uuid.UUID, task_id: uuid.UUID
) -> Task | None:
    """The task, only if it lives in ``workspace_id``."""
    return session.scalars(
        select(Task).where(Task.id == task_id, Task.workspace_id == workspace_id)
    ).first()


def get_link(
    session: Session, *, workspace_id: uuid.UUID, blocked_id: uuid.UUID, blocking_id: uuid.UUID
) -> TaskDependency | None:
    return session.scalars(
        select(TaskDependency).where(
            TaskDependency.workspace_id == workspace_id,
            TaskDependency.blocked_task_id == blocked_id,
            TaskDependency.blocking_task_id == blocking_id,
        )
    ).first()


def count_blockers(session: Session, task_id: uuid.UUID) -> int:
    """How many tasks ``task_id`` waits on, done or not."""
    return (
        session.scalar(
            select(func.count())
            .select_from(TaskDependency)
            .where(TaskDependency.blocked_task_id == task_id)
        )
        or 0
    )


def _open_first(stmt: Select[Task]) -> Select[Task]:
    """Work still to do first, then by title, so a list reads as a to-do list."""
    return stmt.order_by(Task.status == TaskStatus.DONE, Task.title, Task.id)


def blockers_of(session: Session, *, workspace_id: uuid.UUID, task_id: uuid.UUID) -> Sequence[Task]:
    """The tasks ``task_id`` waits on."""
    stmt = (
        select(Task)
        .join(TaskDependency, TaskDependency.blocking_task_id == Task.id)
        .where(
            TaskDependency.workspace_id == workspace_id,
            TaskDependency.blocked_task_id == task_id,
        )
    )
    return session.scalars(_open_first(stmt)).all()


def blocked_by(session: Session, *, workspace_id: uuid.UUID, task_id: uuid.UUID) -> Sequence[Task]:
    """The tasks waiting on ``task_id``."""
    stmt = (
        select(Task)
        .join(TaskDependency, TaskDependency.blocked_task_id == Task.id)
        .where(
            TaskDependency.workspace_id == workspace_id,
            TaskDependency.blocking_task_id == task_id,
        )
    )
    return session.scalars(_open_first(stmt)).all()


def reaches(
    session: Session, *, workspace_id: uuid.UUID, start: uuid.UUID, target: uuid.UUID
) -> bool:
    """Whether ``start`` blocks ``target``, directly or through other tasks.

    A breadth-first walk along "blocks" links, one query per step, that visits
    each task once --- so a long chain or a wide fan-out ends, and a graph that
    somehow already holds a loop cannot spin it.
    """
    seen = {start}
    frontier = {start}
    while frontier:
        nxt = set(
            session.scalars(
                select(TaskDependency.blocked_task_id).where(
                    TaskDependency.workspace_id == workspace_id,
                    TaskDependency.blocking_task_id.in_(list(frontier)),
                )
            ).all()
        )
        if target in nxt:
            return True
        frontier = nxt - seen
        seen |= frontier
    return False


def lock_workspace(session: Session, workspace_id: uuid.UUID) -> None:
    """Serialize dependency writes inside one tenant until the transaction ends.

    Two people linking A to B and B to A at the same instant would each pass the
    cycle check. On PostgreSQL this row lock makes the second wait and then see
    the first link; SQLite already serializes every write, and ignores it.
    """
    session.execute(select(Workspace.id).where(Workspace.id == workspace_id).with_for_update())


def add_link(session: Session, link: TaskDependency) -> None:
    session.add(link)
    session.flush()


def delete_link(session: Session, link: TaskDependency) -> None:
    session.delete(link)


def open_blocker_counts(
    session: Session, task_ids: Collection[uuid.UUID]
) -> Mapping[uuid.UUID, int]:
    """How many *unfinished* tasks each task still waits on, in one grouped query.

    Tasks waiting on nothing open are simply absent.
    """
    if not task_ids:
        return {}
    blocker = aliased(Task)
    rows = session.execute(
        select(TaskDependency.blocked_task_id, func.count())
        .join(blocker, blocker.id == TaskDependency.blocking_task_id)
        .where(
            TaskDependency.blocked_task_id.in_(list(task_ids)),
            blocker.status != TaskStatus.DONE,
        )
        .group_by(TaskDependency.blocked_task_id)
    ).all()
    return {task_id: int(count) for task_id, count in rows}


def unblocked_by(session: Session, finished: Task) -> Sequence[Task]:
    """The unfinished tasks that waited on ``finished`` and now wait on nothing open.

    Read after ``finished`` was flushed as done, so its own row already counts as
    finished here.
    """
    waiting = select(TaskDependency.blocked_task_id).where(
        TaskDependency.workspace_id == finished.workspace_id,
        TaskDependency.blocking_task_id == finished.id,
    )
    blocker = aliased(Task)
    still_blocked = (
        exists()
        .where(TaskDependency.blocked_task_id == Task.id)
        .where(blocker.id == TaskDependency.blocking_task_id)
        .where(blocker.status != TaskStatus.DONE)
    )
    return session.scalars(
        select(Task).where(
            Task.id.in_(waiting),
            Task.status != TaskStatus.DONE,
            ~still_blocked,
        )
    ).all()
