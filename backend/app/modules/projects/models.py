"""SQLAlchemy persistence model for projects.

Baseline schema rules (architecture doc section 6): UUID primary keys,
timezone-aware UTC timestamps, ``created_at``/``updated_at``, explicit indexes
and database constraints for hard invariants.

A project lives in exactly one tenant, like a task: ``workspace_id`` is required
and is the authorization boundary, decided by
``workspaces.access.WorkspaceAccessPolicy``. A project in a personal workspace is
private to its one member.

Names are unique per workspace *regardless of case*. The comparison key is
stored (``name_key``, the name case-folded in Python) under a plain unique
constraint, rather than a ``lower(name)`` expression index, for two reasons:
SQLite's ``lower()`` folds ASCII only while PostgreSQL's folds all of Unicode, so
the sandbox and the canonical database would disagree about "Ärger" and "ärger";
and Alembic cannot reflect expression indexes on SQLite, so one could silently go
missing from a migration. ``name_key`` is derived from ``name`` on every
assignment and is never part of the API. The service checks first for a friendly
error; the constraint is what settles two people creating "Website" and
"website" at the same instant.

``version`` is the optimistic-locking column, as on tasks: renames from two
people at once cannot both win silently (see ``ProjectConflictError``).
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
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.db import Base
from app.shared.time import utc_now

if TYPE_CHECKING:
    from app.modules.users.models import User


#: ``str.casefold`` can lengthen a name (``"ß"`` becomes ``"ss"``), by at most
#: three code points per character.
NAME_KEY_LENGTH = 3 * 120


def name_key(name: str) -> str:
    """The form two project names are compared in: Unicode case-folded."""
    return name.casefold()


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("length(name) > 0", name="ck_projects_name_not_empty"),
        # One name per tenant, case-insensitively. Its leading column also serves
        # every "this workspace's projects" lookup, so no second index.
        UniqueConstraint("workspace_id", "name_key", name="uq_projects_workspace_id_name_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Deleting a tenant deletes its projects, like its tasks.
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "workspaces.id", ondelete="CASCADE", name="fk_projects_workspace_id_workspaces"
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Derived from ``name`` (see ``_derive_name_key``); never set directly.
    name_key: Mapped[str] = mapped_column(String(NAME_KEY_LENGTH), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Kept when the account goes away: the project is the company's.
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL", name="fk_projects_created_by_id_users"),
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
        return f"<Project id={self.id} workspace={self.workspace_id}>"
