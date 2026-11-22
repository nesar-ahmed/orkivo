"""SQLAlchemy persistence model for the activity log.

Baseline schema rules (architecture doc section 6): UUID primary keys,
timezone-aware UTC timestamps, explicit indexes. An event is written once, so it
has ``created_at`` and no ``updated_at``.

Three columns deliberately have no foreign key:

* ``task_id`` --- the log outlives its subject. "Ana deleted *Fix login*" is
  written in the same transaction as the delete; a cascade would remove the
  event with the task, and ``SET NULL`` would be an update to an append-only row.
* ``comment_id`` --- likewise for a deleted comment.
* the snapshots in ``task_title`` and ``changes`` --- names of people and projects
  are copied as they were, so history reads the same after a rename or deletion.

``workspace_id`` *is* a cascading foreign key: nothing outlives the tenant it was
in, the log included. ``actor_id`` is ``SET NULL`` like every other "who did it"
column: accounts are disabled rather than deleted, so in practice it never fires.

Append-only is enforced twice. The repository offers no update or delete, and
the ORM refuses one if any code path tries (``ActivityLogIsAppendOnlyError``).
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Uuid, event
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Mapper, mapped_column, relationship

from app.core.db import Base
from app.modules.activity.enums import ActivityVerb
from app.modules.activity.exceptions import ActivityLogIsAppendOnlyError
from app.shared.time import utc_now

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

    from app.modules.users.models import User


def _stored_values(enum: type[StrEnum]) -> list[str]:
    """Store enum *values*, so renaming a member cannot silently change data."""
    return [member.value for member in enum]


#: JSON everywhere, JSONB on PostgreSQL (indexable, compact, the canonical choice).
ChangesJSON = JSON().with_variant(JSONB(), "postgresql")


class ActivityEvent(Base):
    __tablename__ = "activity_events"
    __table_args__ = (
        # One task's history, newest first.
        Index("ix_activity_events_task_id_created_at", "task_id", "created_at"),
        # One workspace's feed, newest first --- including deleted tasks.
        Index("ix_activity_events_workspace_id_created_at", "workspace_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "workspaces.id",
            ondelete="CASCADE",
            name="fk_activity_events_workspace_id_workspaces",
        ),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL", name="fk_activity_events_actor_id_users"),
        nullable=True,
    )
    verb: Mapped[ActivityVerb] = mapped_column(
        SqlEnum(
            ActivityVerb,
            name="activity_verb",
            native_enum=False,
            validate_strings=True,
            values_callable=_stored_values,
            length=32,
        ),
        nullable=False,
    )
    # No foreign keys: see the module docstring.
    task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    comment_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    task_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # The task's version *after* this change, so an event can be matched to the
    # version a client saw --- and to the save that a conflict refused.
    task_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    changes: Mapped[dict[str, Any]] = mapped_column(ChangesJSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_id], lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        # No titles or field values: content must not reach logs.
        return f"<ActivityEvent id={self.id} verb={self.verb.value}>"


@event.listens_for(ActivityEvent, "before_update")
def _refuse_update(_mapper: Mapper[Any], _connection: "Connection", _target: object) -> None:
    raise ActivityLogIsAppendOnlyError("update")


@event.listens_for(ActivityEvent, "before_delete")
def _refuse_delete(_mapper: Mapper[Any], _connection: "Connection", _target: object) -> None:
    raise ActivityLogIsAppendOnlyError("delete")
