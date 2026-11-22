"""SQLAlchemy persistence model for task dependencies.

Baseline schema rules (architecture doc section 6): UUID primary keys,
timezone-aware UTC timestamps, explicit indexes and database constraints for hard
invariants. A link is created or deleted, never changed, so it has
``created_at`` and no ``updated_at``.

One row says "``blocking_task_id`` must be done before ``blocked_task_id``". Both
tasks are in the row's ``workspace_id`` --- the authorization boundary, carried
so every query keeps the tenant predicate without a join, like comments. That
"same workspace" is the service's check on every write: a foreign key cannot say
"a task of *this* tenant". The database still refuses a task blocking itself and
the same link twice. Deleting either task deletes the link; deleting the tenant
deletes them all. Cycles are the service's to refuse, since no constraint can
see a path through several rows.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.shared.time import utc_now

if TYPE_CHECKING:
    from app.modules.users.models import User


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (
        CheckConstraint(
            "blocked_task_id <> blocking_task_id", name="ck_task_dependencies_not_self"
        ),
        # One link per pair. Its leading column also serves "what is this task
        # waiting on", so no second index for that.
        UniqueConstraint(
            "blocked_task_id", "blocking_task_id", name="uq_task_dependencies_blocked_blocking"
        ),
        # "What is this task holding up": the other direction, and the lookup that
        # finds who is unblocked when a task is done.
        Index("ix_task_dependencies_blocking_task_id", "blocking_task_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "workspaces.id",
            ondelete="CASCADE",
            name="fk_task_dependencies_workspace_id_workspaces",
        ),
        nullable=False,
        index=True,
    )
    blocked_task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "tasks.id", ondelete="CASCADE", name="fk_task_dependencies_blocked_task_id_tasks"
        ),
        nullable=False,
    )
    blocking_task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "tasks.id", ondelete="CASCADE", name="fk_task_dependencies_blocking_task_id_tasks"
        ),
        nullable=False,
    )
    # Kept when the account goes away: the plan is the company's.
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "users.id", ondelete="SET NULL", name="fk_task_dependencies_created_by_id_users"
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_id])

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<TaskDependency blocked={self.blocked_task_id} by={self.blocking_task_id}>"
