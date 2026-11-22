"""add projects

Projects arrive as named groups of work inside one workspace:

* ``projects`` --- one tenant's projects (``CASCADE`` with the workspace, like its
  tasks), with an optimistic-locking ``version`` as on tasks. Names are unique
  per workspace regardless of case through ``name_key``: the name case-folded by
  the application, under a plain unique constraint. An expression index on
  ``lower(name)`` was rejected because SQLite's ``lower()`` folds ASCII only
  while PostgreSQL's folds all of Unicode, and because Alembic cannot reflect
  such an index on SQLite, so it could drift unnoticed.
* ``tasks.project_id`` --- nullable, because a task need not belong to a
  project. ``SET NULL`` is only a safety net: deleting a project detaches its
  tasks explicitly in the same transaction, bumping their versions.
  ``ix_tasks_workspace_id_project_id`` serves one project's tasks, its counts,
  and that detach.

"The project is in the task's own workspace" is checked by the service on every
write, for the same reason as a task's assignee: a composite foreign key would
need ``ON DELETE SET NULL`` for one of its two columns only.

Both tables start empty of links, so there is nothing to backfill.

Revision ID: 128ad2d75e66
Revises: a33c21c35556
Create Date: 2026-11-05

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "128ad2d75e66"
down_revision: str | Sequence[str] | None = "a33c21c35556"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("name_key", sa.String(length=360), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(name) > 0", name="ck_projects_name_not_empty"),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_projects_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_projects_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "name_key", name="uq_projects_workspace_id_name_key"),
    )
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("project_id", sa.Uuid(), nullable=True))
        batch_op.create_index(
            "ix_tasks_workspace_id_project_id", ["workspace_id", "project_id"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_tasks_project_id_projects",
            "projects",
            ["project_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    """Downgrade schema. Loses every project and which task was filed under it."""
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_constraint("fk_tasks_project_id_projects", type_="foreignkey")
        batch_op.drop_index("ix_tasks_workspace_id_project_id")
        batch_op.drop_column("project_id")

    op.drop_table("projects")
