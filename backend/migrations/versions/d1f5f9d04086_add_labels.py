"""add labels

Labels arrive as named, colored tags inside one workspace:

* ``labels`` --- one tenant's labels (``CASCADE`` with the workspace, like its
  projects), with an optimistic-locking ``version``. Names are unique per
  workspace regardless of case through ``name_key``, the name case-folded by the
  application, under a plain unique constraint --- the design ``projects`` uses,
  for the same reasons (SQLite's ``lower()`` folds ASCII only, and Alembic cannot
  reflect expression indexes on SQLite). ``color`` is one of a fixed palette of
  names, stored as a string like every other enum here.
* ``task_labels`` --- which labels each task carries. The composite primary key
  makes a duplicate tag impossible and serves "this task's labels";
  ``ix_task_labels_label_id`` serves the label filter, the per-label counts and
  taking a deleted label off its tasks. Both foreign keys cascade, but only as a
  safety net: deleting a label takes it off its tasks explicitly in the same
  transaction, bumping their versions and recording the change.

"The label is in the task's own workspace" is checked by the service on every
write, for the same reason as a task's project: the link table would need the
task's ``workspace_id`` on both sides to say it as a constraint.

Both tables start empty, so there is nothing to backfill.

Revision ID: d1f5f9d04086
Revises: 550e54b0c1b2
Create Date: 2026-11-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1f5f9d04086"
down_revision: str | Sequence[str] | None = "550e54b0c1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Spelled out rather than imported from the application: a migration must keep
# working after the palette grows.
_COLORS = (
    "gray",
    "red",
    "orange",
    "yellow",
    "green",
    "teal",
    "blue",
    "indigo",
    "purple",
    "pink",
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "labels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("name_key", sa.String(length=150), nullable=False),
        sa.Column(
            "color",
            sa.Enum(*_COLORS, name="label_color", native_enum=False),
            nullable=False,
        ),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(name) > 0", name="ck_labels_name_not_empty"),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_labels_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_labels_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "name_key", name="uq_labels_workspace_id_name_key"),
    )
    op.create_table(
        "task_labels",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("label_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["label_id"],
            ["labels.id"],
            name="fk_task_labels_label_id_labels",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name="fk_task_labels_task_id_tasks",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("task_id", "label_id", name="pk_task_labels"),
    )
    with op.batch_alter_table("task_labels", schema=None) as batch_op:
        batch_op.create_index("ix_task_labels_label_id", ["label_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema. Loses every label and which task carried it."""
    with op.batch_alter_table("task_labels", schema=None) as batch_op:
        batch_op.drop_index("ix_task_labels_label_id")

    op.drop_table("task_labels")
    op.drop_table("labels")
