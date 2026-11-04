"""Database access for the tasks module.

The repository encapsulates queries only. It does not decide authorization
policy and does not return HTTP responses; transaction commits happen at the
service layer (architecture doc sections 4.1 and 6.2).
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.modules.tasks.enums import TaskPriority, TaskStatus
from app.modules.tasks.models import Task


def list_tasks(
    session: Session,
    *,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[Sequence[Task], int]:
    """Return one page of tasks plus the total matching count."""
    stmt: Select[Task] = select(Task).order_by(Task.created_at.desc(), Task.id.desc())
    if status is not None:
        stmt = stmt.where(Task.status == status)
    if priority is not None:
        stmt = stmt.where(Task.priority == priority)
    if search:
        stmt = stmt.where(
            or_(
                # icontains escapes LIKE wildcards (% and _) in user input.
                Task.title.icontains(search, autoescape=True),
                Task.description.icontains(search, autoescape=True),
            )
        )

    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = session.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return items, total


def get_task(session: Session, task_id: uuid.UUID) -> Task | None:
    return session.get(Task, task_id)


def add_task(session: Session, task: Task) -> None:
    session.add(task)
    session.flush()


def delete_task(session: Session, task: Task) -> None:
    session.delete(task)
