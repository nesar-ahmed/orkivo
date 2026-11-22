"""Database access for the activity log: append, and read.

There is deliberately no update or delete here. The service decides who may
read; every read still carries the tenant predicate, so a page of history can
only ever come from the one workspace that was authorized (architecture doc
sections 4.1, 6.2 and 9).
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.modules.activity.models import ActivityEvent


def append(session: Session, event: ActivityEvent) -> None:
    """Add an event to the caller's unit of work. Never flushes or commits."""
    session.add(event)


def list_events(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[Sequence[ActivityEvent], int]:
    """One page of a workspace's events --- or one task's --- newest first."""
    stmt: Select[ActivityEvent] = (
        select(ActivityEvent)
        .where(ActivityEvent.workspace_id == workspace_id)
        .order_by(ActivityEvent.created_at.desc(), ActivityEvent.id.desc())
    )
    if task_id is not None:
        stmt = stmt.where(ActivityEvent.task_id == task_id)
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = session.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return items, total
