"""SQLAlchemy persistence model for labels.

Baseline schema rules (architecture doc section 6): UUID primary keys,
timezone-aware UTC timestamps, ``created_at``/``updated_at``, explicit indexes
and database constraints for hard invariants.

A label lives in exactly one tenant, like a project: ``workspace_id`` is required
and is the authorization boundary, decided by
``workspaces.access.WorkspaceAccessPolicy``. A label in a personal workspace is
private to its one member.

Names are unique per workspace *regardless of case*, through a stored
comparison key under a plain unique constraint --- the same design as
``projects.models`` and for the same reasons: SQLite's ``lower()`` folds ASCII
only while PostgreSQL's folds all of Unicode, and Alembic cannot reflect
expression indexes on SQLite. ``name_key`` is derived from ``name`` on every
assignment and is never part of the API.

Which tasks carry a label is the tasks module's table (``task_labels``), so this
model has no relationship to tasks at all.

``version`` is the optimistic-locking column, as on tasks and projects: two
people renaming or recoloring a label at once cannot both win silently (see
``LabelConflictError``).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.db import Base
from app.modules.labels.enums import LabelColor
from app.shared.time import utc_now

if TYPE_CHECKING:
    from app.modules.users.models import User

#: Mirrors the request contract, so the database refuses what the API would.
NAME_MAX_LENGTH = 50

#: ``str.casefold`` can lengthen a name (``"ß"`` becomes ``"ss"``), by at most
#: three code points per character.
NAME_KEY_LENGTH = 3 * NAME_MAX_LENGTH


def name_key(name: str) -> str:
    """The form two label names are compared in: Unicode case-folded."""
    return name.casefold()


class Label(Base):
    __tablename__ = "labels"
    __table_args__ = (
        CheckConstraint("length(name) > 0", name="ck_labels_name_not_empty"),
        # One name per tenant, case-insensitively. Its leading column also serves
        # every "this workspace's labels" lookup, so no second index.
        UniqueConstraint("workspace_id", "name_key", name="uq_labels_workspace_id_name_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Deleting a tenant deletes its labels, like its tasks and projects.
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE", name="fk_labels_workspace_id_workspaces"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH), nullable=False)
    # Derived from ``name`` (see ``_derive_name_key``); never set directly.
    name_key: Mapped[str] = mapped_column(String(NAME_KEY_LENGTH), nullable=False)
    color: Mapped[LabelColor] = mapped_column(
        SqlEnum(
            LabelColor,
            name="label_color",
            native_enum=False,
            validate_strings=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=LabelColor.GRAY,
    )
    # Kept when the account goes away: the label is the company's.
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL", name="fk_labels_created_by_id_users"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_id], lazy="joined")

    __mapper_args__ = {"version_id_col": version}

    @validates("name")
    def _derive_name_key(self, _key: str, value: str) -> str:
        """Keep the comparison key in step with every write of the name."""
        self.name_key = name_key(value)
        return value

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Label id={self.id} workspace={self.workspace_id}>"
