"""Database access for watchers and notifications.

Queries only; the service and the notifier decide who is told what. Every inbox
read carries the recipient *and* a current-membership predicate, so a notification
from a workspace the recipient has left can never be returned (architecture doc
sections 4.1, 6.2 and 9).
"""

import uuid
from collections.abc import Collection, Sequence
from typing import Any

from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.modules.notifications.models import Notification, TaskWatcher
from app.modules.tasks.models import Task
from app.modules.users.models import User
from app.modules.workspaces.models import WorkspaceMember
from app.shared.time import utc_now


# --- watchers ------------------------------------------------------------------
def add_watchers(session: Session, task_id: uuid.UUID, user_ids: Collection[uuid.UUID]) -> None:
    """Make each account watch the task; already watching is not an error.

    ``INSERT ... ON CONFLICT DO NOTHING`` on the unique ``(task_id, user_id)``, so
    two comments posted at the same instant by the same person cannot fail on
    the second watcher row. Both supported databases have it, spelled through
    their own dialect.
    """
    if not user_ids:
        return
    rows = [
        {"id": uuid.uuid4(), "task_id": task_id, "user_id": user_id, "created_at": utc_now()}
        for user_id in dict.fromkeys(user_ids)
    ]
    dialect = session.get_bind().dialect.name
    insert: Any = postgresql_insert if dialect == "postgresql" else sqlite_insert
    session.execute(
        insert(TaskWatcher)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["task_id", "user_id"])
    )


def remove_watcher(session: Session, task_id: uuid.UUID, user_id: uuid.UUID) -> None:
    session.execute(
        delete(TaskWatcher).where(TaskWatcher.task_id == task_id, TaskWatcher.user_id == user_id)
    )


def watcher_ids(session: Session, task_id: uuid.UUID) -> set[uuid.UUID]:
    return set(session.scalars(select(TaskWatcher.user_id).where(TaskWatcher.task_id == task_id)))


def list_watchers(session: Session, task_id: uuid.UUID) -> Sequence[User]:
    """The accounts watching a task, by name."""
    return session.scalars(
        select(User)
        .join(TaskWatcher, TaskWatcher.user_id == User.id)
        .where(TaskWatcher.task_id == task_id)
        .order_by(func.lower(User.display_name), User.id)
    ).all()


# --- notifications ---------------------------------------------------------------
def add_notification(session: Session, notification: Notification) -> None:
    """Add to the caller's unit of work. Never flushes or commits."""
    session.add(notification)


def _inbox(recipient_id: uuid.UUID) -> Select[Notification]:
    """The recipient's notifications, from workspaces they still belong to."""
    still_member = select(WorkspaceMember.workspace_id).where(
        WorkspaceMember.user_id == recipient_id
    )
    return select(Notification).where(
        Notification.recipient_id == recipient_id,
        Notification.workspace_id.in_(still_member),
    )


def list_inbox(
    session: Session,
    *,
    recipient_id: uuid.UUID,
    unread_only: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> tuple[Sequence[Notification], int]:
    """One page of an inbox, newest first, plus the total matching count."""
    stmt = _inbox(recipient_id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = session.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return items, total


def count_unread(session: Session, recipient_id: uuid.UUID) -> int:
    stmt = _inbox(recipient_id).where(Notification.read_at.is_(None))
    return session.scalar(select(func.count()).select_from(stmt.subquery())) or 0


def get_notification(session: Session, notification_id: uuid.UUID) -> Notification | None:
    return session.get(Notification, notification_id)


def mark_all_read(session: Session, recipient_id: uuid.UUID) -> int:
    """Mark every unread notification of one recipient read; return how many."""
    read = session.scalars(
        update(Notification)
        .where(Notification.recipient_id == recipient_id, Notification.read_at.is_(None))
        .values(read_at=utc_now())
        .returning(Notification.id),
        execution_options={"synchronize_session": False},
    ).all()
    for notification_id in read:
        loaded = session.identity_map.get(Session.identity_key(Notification, notification_id))
        if loaded is not None:
            session.expire(loaded)
    return len(read)


# --- membership ending -----------------------------------------------------------
def forget_member(session: Session, *, workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Stop ``user_id`` watching the workspace's tasks and clear their inbox of it."""
    tasks_here = select(Task.id).where(Task.workspace_id == workspace_id)
    session.execute(
        delete(TaskWatcher)
        .where(TaskWatcher.user_id == user_id, TaskWatcher.task_id.in_(tasks_here))
        .execution_options(synchronize_session=False)
    )
    session.execute(
        delete(Notification)
        .where(Notification.recipient_id == user_id, Notification.workspace_id == workspace_id)
        .execution_options(synchronize_session=False)
    )
