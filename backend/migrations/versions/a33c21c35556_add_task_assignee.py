"""add task assignee

A task can now be assigned to one person, who is expected to do the work:

* ``assignee_id`` --- nullable, because most tasks start unassigned and
  "nobody yet" is a real state rather than a missing value. ``SET NULL`` if the
  account goes, like ``updated_by_id``: the task belongs to the company.
* ``ix_tasks_workspace_id_assignee_id`` --- "assigned to me / to Ana / to
  nobody" inside one tenant, and the lookup that releases a departing member's
  assignments.

"The assignee is a member of the task's workspace" is deliberately *not* a
database constraint. A composite foreign key onto ``workspace_members`` would
need ``ON DELETE SET NULL`` for the assignee column only, which SQLite cannot
express; the service checks membership on every write instead, and releases
assignments in the same transaction that ends a membership.

Existing rows start unassigned. No backfill needed.

Revision ID: a33c21c35556
Revises: 37f7d50e6d2a
Create Date: 2026-11-05

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a33c21c35556"
down_revision: str | Sequence[str] | None = "37f7d50e6d2a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("assignee_id", sa.Uuid(), nullable=True))
        batch_op.create_index(
            "ix_tasks_workspace_id_assignee_id", ["workspace_id", "assignee_id"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_tasks_assignee_id_users",
            "users",
            ["assignee_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    """Downgrade schema. Loses only who each task was assigned to."""
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_constraint("fk_tasks_assignee_id_users", type_="foreignkey")
        batch_op.drop_index("ix_tasks_workspace_id_assignee_id")
        batch_op.drop_column("assignee_id")
