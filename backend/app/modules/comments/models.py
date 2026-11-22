"""SQLAlchemy persistence model for comments.

Baseline schema rules (architecture doc section 6): UUID primary keys,
timezone-aware UTC timestamps, explicit indexes and database constraints for hard
invariants.

A comment lives on one task and is deleted with it. It also carries the task's
``workspace_id`` --- the authorization boundary --- so every query can apply the
tenant predicate without a join, exactly like tasks and projects do. The author
is ``SET NULL``: the conversation belongs to the company, not to its authors.

``edited_at`` is set when the author changes the text, so readers can see that a
comment is not what it first said.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.shared.time import utc_now

if TYPE_CHECKING:
    from app.modules.tasks.models import Task
    from app.modules.users.models import User

#: Mirrors the request contract, so the database refuses what the API would.
MAX_BODY_LENGTH = 10_000


class TaskComment(Base):
    __tablename__ = "task_comments"
    __table_args__ = (
        CheckConstraint("length(body) > 0", name="ck_task_comments_body_not_empty"),
        CheckConstraint(
            f"length(body) <= {MAX_BODY_LENGTH}", name="ck_task_comments_body_bounded"
        ),
        # One task's conversation, oldest first.
        Index("ix_task_comments_task_id_created_at", "task_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tasks.id", ondelete="CASCADE", name="fk_task_comments_task_id_tasks"),
        nullable=False,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "workspaces.id", ondelete="CASCADE", name="fk_task_comments_workspace_id_workspaces"
        ),
        nullable=False,
        index=True,
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL", name="fk_task_comments_author_id_users"),
        nullable=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # Joined on every read: a comment is never shown without its author.
    author: Mapped["User | None"] = relationship(foreign_keys=[author_id], lazy="joined")
    task: Mapped["Task"] = relationship(foreign_keys=[task_id])

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        # Never the body: private content must not reach logs.
        return f"<TaskComment id={self.id} task={self.task_id}>"
