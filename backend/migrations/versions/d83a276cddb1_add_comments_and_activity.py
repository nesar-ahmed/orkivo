"""add comments and activity

Two tables, both new, so nothing existing is touched:

* ``task_comments`` --- the conversation on a task. Deleted with the task
  (``CASCADE``) and with the workspace; it also carries the task's
  ``workspace_id``, so every query keeps the tenant predicate without a join.
  The author is ``SET NULL``. The body is bounded (1 to 10 000 characters) by
  the database as well as the API.
* ``activity_events`` --- the append-only log, written by task and comment
  changes in the same transaction as the change. ``task_id`` and
  ``comment_id`` deliberately have *no* foreign key: an event describing a
  deletion is written in the deleting transaction, and must outlive its subject
  without ever being updated (``SET NULL`` would be an update). Only the
  workspace cascades. ``changes`` is JSON (JSONB on PostgreSQL).

No history is invented for tasks that existed before this revision: their log
starts with the first change made after it.

Revision ID: d83a276cddb1
Revises: 128ad2d75e66
Create Date: 2026-11-05

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d83a276cddb1"
down_revision: str | Sequence[str] | None = "128ad2d75e66"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Spelled out rather than imported from the application: a migration must keep
# working after the enum grows.
_VERBS = (
    "task.created",
    "task.updated",
    "task.deleted",
    "comment.added",
    "comment.edited",
    "comment.deleted",
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "activity_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column(
            "verb",
            sa.Enum(*_VERBS, name="activity_verb", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("comment_id", sa.Uuid(), nullable=True),
        sa.Column("task_title", sa.String(length=200), nullable=True),
        sa.Column("task_version", sa.Integer(), nullable=True),
        sa.Column(
            "changes",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name="fk_activity_events_actor_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_activity_events_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("activity_events", schema=None) as batch_op:
        batch_op.create_index(
            "ix_activity_events_task_id_created_at", ["task_id", "created_at"], unique=False
        )
        batch_op.create_index(
            "ix_activity_events_workspace_id_created_at",
            ["workspace_id", "created_at"],
            unique=False,
        )

    op.create_table(
        "task_comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(body) <= 10000", name="ck_task_comments_body_bounded"),
        sa.CheckConstraint("length(body) > 0", name="ck_task_comments_body_not_empty"),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name="fk_task_comments_author_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name="fk_task_comments_task_id_tasks", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_task_comments_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("task_comments", schema=None) as batch_op:
        batch_op.create_index(
            "ix_task_comments_task_id_created_at", ["task_id", "created_at"], unique=False
        )
        batch_op.create_index("ix_task_comments_workspace_id", ["workspace_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema. Loses every comment and the whole activity log."""
    with op.batch_alter_table("task_comments", schema=None) as batch_op:
        batch_op.drop_index("ix_task_comments_workspace_id")
        batch_op.drop_index("ix_task_comments_task_id_created_at")

    op.drop_table("task_comments")
    with op.batch_alter_table("activity_events", schema=None) as batch_op:
        batch_op.drop_index("ix_activity_events_workspace_id_created_at")
        batch_op.drop_index("ix_activity_events_task_id_created_at")

    op.drop_table("activity_events")
