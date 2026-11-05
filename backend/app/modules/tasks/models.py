"""SQLAlchemy persistence model for tasks.

Baseline schema rules (architecture doc section 6): UUID primary keys,
timezone-aware UTC timestamps, ``created_at``/``updated_at``, explicit
indexes and database constraints for hard invariants.

Every task belongs to the user that created it. ``owner_id`` is not null and is
part of the primary lookup path for every read, so cross-user data cannot leak
through a query (architecture doc section 6/9).

The ``workspaces`` module has landed and ``projects`` has not, so a task today is
effectively work in its owner's *personal* tenant: ``owner_id`` is still the
authorization boundary. The next revision adds ``workspace_id`` (backfilled from
each owner's personal workspace, then required) so a company can hold shared
tasks; until then a tenant has members but no content.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    Uuid,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.modules.tasks.enums import TaskPriority, TaskStatus
from app.shared.time import utc_now


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        # Title must hold a non-empty value even if application validation
        # is bypassed (invariant that must survive concurrent requests).
        CheckConstraint("length(title) > 0", name="ck_tasks_title_not_empty"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE", name="fk_tasks_owner_id_users"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        SqlEnum(
            TaskStatus,
            name="task_status",
            native_enum=False,
            validate_strings=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=TaskStatus.TODO,
        index=True,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        SqlEnum(
            TaskPriority,
            name="task_priority",
            native_enum=False,
            validate_strings=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=TaskPriority.MEDIUM,
        index=True,
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Task id={self.id} title={self.title!r} status={self.status.value}>"
