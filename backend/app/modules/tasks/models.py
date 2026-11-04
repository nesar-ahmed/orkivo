"""SQLAlchemy persistence model for tasks.

Baseline schema rules (architecture doc section 6): UUID primary keys,
timezone-aware UTC timestamps, ``created_at``/``updated_at``, explicit
indexes and database constraints for hard invariants.

Note: ``project_id``/``workspace_id`` foreign keys arrive when the
``projects`` and ``workspaces`` modules are added in a later stage.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    String,
    Text,
    Uuid,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.modules.tasks.enums import TaskPriority, TaskStatus


def utc_now() -> datetime:
    """Timezone-aware UTC now, used for Python-side timestamp defaults."""
    return datetime.now(UTC)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        # Title must hold a non-empty value even if application validation
        # is bypassed (invariant that must survive concurrent requests).
        CheckConstraint("length(title) > 0", name="ck_tasks_title_not_empty"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
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
