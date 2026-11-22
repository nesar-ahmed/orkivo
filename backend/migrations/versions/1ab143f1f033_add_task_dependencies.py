"""add task dependencies

One new table, so nothing existing is touched:

* ``task_dependencies`` --- "this task waits on that one". Both tasks are in the
  row's ``workspace_id``, carried so every query keeps the tenant predicate
  without a join; the service checks that on every write. The database refuses a
  task waiting on itself (``ck_task_dependencies_not_self``) and the same link
  twice (``uq_task_dependencies_blocked_blocking``, which also serves "what does
  this task wait on"). ``ix_task_dependencies_blocking_task_id`` serves the other
  direction and finding who is unblocked when a task is done. Deleting either
  task, or the workspace, deletes the link; the creator is ``SET NULL``.

Cycles are refused by the service, since no constraint can see a path through
several rows. The table starts empty, so there is nothing to backfill. The
``unblocked`` notification kind and the ``dependency.*`` activity verbs are new
enum values in existing string columns that already fit them.

Revision ID: 1ab143f1f033
Revises: faaf19c266bd
Create Date: 2026-11-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1ab143f1f033"
down_revision: str | Sequence[str] | None = "faaf19c266bd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "task_dependencies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("blocked_task_id", sa.Uuid(), nullable=False),
        sa.Column("blocking_task_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "blocked_task_id <> blocking_task_id", name="ck_task_dependencies_not_self"
        ),
        sa.ForeignKeyConstraint(
            ["blocked_task_id"],
            ["tasks.id"],
            name="fk_task_dependencies_blocked_task_id_tasks",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["blocking_task_id"],
            ["tasks.id"],
            name="fk_task_dependencies_blocking_task_id_tasks",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_task_dependencies_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_task_dependencies_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "blocked_task_id", "blocking_task_id", name="uq_task_dependencies_blocked_blocking"
        ),
    )
    with op.batch_alter_table("task_dependencies", schema=None) as batch_op:
        batch_op.create_index(
            "ix_task_dependencies_blocking_task_id", ["blocking_task_id"], unique=False
        )
        batch_op.create_index("ix_task_dependencies_workspace_id", ["workspace_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema. Loses every dependency between tasks."""
    with op.batch_alter_table("task_dependencies", schema=None) as batch_op:
        batch_op.drop_index("ix_task_dependencies_workspace_id")
        batch_op.drop_index("ix_task_dependencies_blocking_task_id")

    op.drop_table("task_dependencies")
