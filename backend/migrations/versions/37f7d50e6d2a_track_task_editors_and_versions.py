"""track task editors and versions

Shared company tasks are edited by several people, so each task now records:

* ``updated_by_id`` --- who changed it last (``SET NULL`` if that account goes,
  because the task belongs to the company, not to its editor);
* ``version`` --- an optimistic-locking counter. Every update is issued as
  ``WHERE version = ?`` and increments it, so a stale save is refused with
  ``409 TASK_CONFLICT`` instead of silently undoing a colleague's change.

Existing rows start at version 1 (server default) with no recorded editor, which
is exactly what "never edited since this was tracked" means. No backfill needed.

Revision ID: 37f7d50e6d2a
Revises: 904c9f2a9008
Create Date: 2026-11-05

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "37f7d50e6d2a"
down_revision: str | Sequence[str] | None = "904c9f2a9008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("updated_by_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch_op.create_foreign_key(
            "fk_tasks_updated_by_id_users",
            "users",
            ["updated_by_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    """Downgrade schema. Loses only the editor and version history."""
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_constraint("fk_tasks_updated_by_id_users", type_="foreignkey")
        batch_op.drop_column("version")
        batch_op.drop_column("updated_by_id")
