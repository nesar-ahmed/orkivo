"""Persistence models for watchers and notifications.

Baseline schema rules (architecture doc section 6): UUID primary keys,
timezone-aware UTC timestamps, explicit indexes and database constraints for hard
invariants.

Both tables belong to a task and go with it (``CASCADE``): there is nothing to
follow, and nothing to be told about, once the task is deleted --- its history
stays in the activity log. A notification about a comment goes with the comment
too, so deleting a comment really removes what it said from every inbox.

A person is never notified about their own action. The service never creates
such a row, and ``ck_notifications_not_self`` makes that true even if it tried.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.modules.notifications.enums import NotificationKind
from app.shared.time import utc_now

if TYPE_CHECKING:
    from app.modules.comments.models import TaskComment
    from app.modules.tasks.models import Task
    from app.modules.users.models import User
    from app.modules.workspaces.models import Workspace


def _stored_values(enum: type[StrEnum]) -> list[str]:
    """Store enum *values*, so renaming a member cannot silently change data."""
    return [member.value for member in enum]


class TaskWatcher(Base):
    """One person following one task: they hear about its comments."""

    __tablename__ = "task_watchers"
    __table_args__ = (
        # Watching twice means nothing more; inserts rely on this to be idempotent.
        UniqueConstraint("task_id", "user_id", name="uq_task_watchers_task_id_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tasks.id", ondelete="CASCADE", name="fk_task_watchers_task_id_tasks"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE", name="fk_task_watchers_user_id_users"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    user: Mapped["User"] = relationship(foreign_keys=[user_id], lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<TaskWatcher task={self.task_id} user={self.user_id}>"


class Notification(Base):
    """One thing one person should know about, until they have seen it."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "actor_id IS NULL OR actor_id <> recipient_id", name="ck_notifications_not_self"
        ),
        # The inbox and its unread count: one person's, unread first, newest first.
        Index(
            "ix_notifications_recipient_id_read_at_created_at",
            "recipient_id",
            "read_at",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE", name="fk_notifications_recipient_id_users"),
        nullable=False,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "workspaces.id", ondelete="CASCADE", name="fk_notifications_workspace_id_workspaces"
        ),
        nullable=False,
        index=True,
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tasks.id", ondelete="CASCADE", name="fk_notifications_task_id_tasks"),
        nullable=False,
        index=True,
    )
    comment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "task_comments.id", ondelete="CASCADE", name="fk_notifications_comment_id_task_comments"
        ),
        nullable=True,
        index=True,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL", name="fk_notifications_actor_id_users"),
        nullable=True,
    )
    kind: Mapped[NotificationKind] = mapped_column(
        SqlEnum(
            NotificationKind,
            name="notification_kind",
            native_enum=False,
            validate_strings=True,
            values_callable=_stored_values,
        ),
        nullable=False,
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    # Joined on every read: an inbox row always shows who, what and where.
    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_id], lazy="joined")
    task: Mapped["Task"] = relationship(foreign_keys=[task_id], lazy="joined")
    workspace: Mapped["Workspace"] = relationship(foreign_keys=[workspace_id], lazy="joined")
    comment: Mapped["TaskComment | None"] = relationship(foreign_keys=[comment_id])

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Notification id={self.id} kind={self.kind.value}>"
