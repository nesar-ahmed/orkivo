"""index tasks by due date

Two indexes for the reads that arrive with "My tasks" and the calendar; no
column changes, so nothing to backfill:

* ``ix_tasks_workspace_id_due_date`` --- one tenant's calendar: the tasks due
  inside a window of dates (``due_from`` / ``due_to``), and a board sorted by
  due date.
* ``ix_tasks_assignee_id_due_date`` --- one person's own list across every tenant
  they are in, soonest due first. ``ix_tasks_workspace_id_assignee_id`` leads
  with the tenant, so it cannot serve a query that spans several.

Revision ID: faaf19c266bd
Revises: d1f5f9d04086
Create Date: 2026-11-06

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "faaf19c266bd"
down_revision: str | Sequence[str] | None = "d1f5f9d04086"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.create_index(
            "ix_tasks_workspace_id_due_date", ["workspace_id", "due_date"], unique=False
        )
        batch_op.create_index(
            "ix_tasks_assignee_id_due_date", ["assignee_id", "due_date"], unique=False
        )


def downgrade() -> None:
    """Downgrade schema. Loses only the two indexes."""
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_index("ix_tasks_assignee_id_due_date")
        batch_op.drop_index("ix_tasks_workspace_id_due_date")
