"""Database access for comments.

Queries only; the service decides who may read or change a comment. Every list
carries the tenant predicate as well as the task, so a page of comments can only
come from the workspace that was authorized (architecture doc sections 4.1, 6.2
and 9).
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.modules.comments.models import TaskComment


def list_comments(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
) -> tuple[Sequence[TaskComment], int]:
    """One page of a task's comments, oldest first --- the order a conversation reads."""
    stmt: Select[TaskComment] = (
        select(TaskComment)
        .where(TaskComment.workspace_id == workspace_id, TaskComment.task_id == task_id)
        .order_by(TaskComment.created_at, TaskComment.id)
    )
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = session.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return items, total


def get_comment(session: Session, comment_id: uuid.UUID) -> TaskComment | None:
    """Fetch a comment by id, *before* authorization (see ``tasks.repository.get_task``)."""
    return session.get(TaskComment, comment_id)


def add_comment(session: Session, comment: TaskComment) -> None:
    session.add(comment)
    session.flush()


def delete_comment(session: Session, comment: TaskComment) -> None:
    session.delete(comment)
