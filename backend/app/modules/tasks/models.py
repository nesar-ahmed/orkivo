"""SQLAlchemy persistence model for tasks.

Baseline schema rules (architecture doc section 6): UUID primary keys,
timezone-aware UTC timestamps, ``created_at``/``updated_at``, explicit
indexes and database constraints for hard invariants.

Every task lives in exactly one tenant. ``workspace_id`` is required and is the
authorization boundary: a caller reaches a task only through membership of that
workspace, decided by ``workspaces.access.WorkspaceAccessPolicy`` (architecture
doc sections 6 and 9). A task in a *personal* workspace is therefore private to
its one member, and a task in a company is shared by all of the company's members.

``owner_id`` records who created the task and ``updated_by_id`` who last changed
it. Neither decides who may see it --- a colleague edits and deletes company tasks
they did not create. The API shows both people by name, never the raw ids.

``version`` is SQLAlchemy's optimistic-locking column: every UPDATE is issued as
``... WHERE id = ? AND version = ?`` and bumps it, so two colleagues saving the
same task at once cannot both win silently (see ``TaskConflictError``).
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.modules.tasks.enums import TaskPriority, TaskStatus
from app.shared.time import utc_now

if TYPE_CHECKING:
    from app.modules.users.models import User


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        # Title must hold a non-empty value even if application validation
        # is bypassed (invariant that must survive concurrent requests).
        CheckConstraint("length(title) > 0", name="ck_tasks_title_not_empty"),
        # The board query: one tenant's tasks, newest first. The leading column
        # also serves every plain ``workspace_id`` lookup, so no second index.
        Index("ix_tasks_workspace_id_created_at", "workspace_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Deleting a tenant deletes its work; nothing outlives the company it was in.
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE", name="fk_tasks_workspace_id_workspaces"),
        nullable=False,
    )
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
    # Kept when the editor's account goes away: the task is the company's.
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL", name="fk_tasks_updated_by_id_users"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # Joined on every read: a task is never shown without its people, and one
    # LEFT JOIN beats a query per row on a board.
    created_by: Mapped["User | None"] = relationship(foreign_keys=[owner_id], lazy="joined")
    updated_by: Mapped["User | None"] = relationship(foreign_keys=[updated_by_id], lazy="joined")

    __mapper_args__ = {"version_id_col": version}

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Task id={self.id} title={self.title!r} status={self.status.value}>"
