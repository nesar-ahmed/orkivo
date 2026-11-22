"""add watchers and notifications

Two new tables, and a backfill so existing work behaves like new work:

* ``task_watchers`` --- who follows a task. One row per person per task
  (``uq_task_watchers_task_id_user_id``, which also makes watching idempotent).
  Goes with the task and with the account.
* ``notifications`` --- the inbox. Goes with its task, its comment (deleting a
  comment removes it from every inbox) and its workspace; the actor is
  ``SET NULL``. ``ck_notifications_not_self`` makes "nobody is told about their
  own action" a database rule. ``ix_notifications_recipient_id_read_at_created_at``
  serves the inbox and its unread count.

Backfill: from now on, creating, being assigned and commenting all make a person
watch a task. Existing tasks get the same watchers they would have had --- their
creator, their assignee and everyone who commented --- but only people who are
*still members* of the task's workspace, so nobody who left a company starts
hearing about it. No notifications are invented for past events.

Revision ID: 550e54b0c1b2
Revises: d83a276cddb1
Create Date: 2026-11-05

"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "550e54b0c1b2"
down_revision: str | Sequence[str] | None = "d83a276cddb1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Spelled out rather than imported from the application: a migration must keep
# working after the enum grows.
_KINDS = ("assigned", "commented", "mentioned")

# Declared with just the columns this revision reads or writes.
_tasks = sa.table(
    "tasks",
    sa.column("id", sa.Uuid()),
    sa.column("workspace_id", sa.Uuid()),
    sa.column("owner_id", sa.Uuid()),
    sa.column("assignee_id", sa.Uuid()),
)
_comments = sa.table(
    "task_comments",
    sa.column("task_id", sa.Uuid()),
    sa.column("author_id", sa.Uuid()),
)
_members = sa.table(
    "workspace_members",
    sa.column("workspace_id", sa.Uuid()),
    sa.column("user_id", sa.Uuid()),
)
_watchers = sa.table(
    "task_watchers",
    sa.column("id", sa.Uuid()),
    sa.column("task_id", sa.Uuid()),
    sa.column("user_id", sa.Uuid()),
    sa.column("created_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "task_watchers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name="fk_task_watchers_task_id_tasks", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_task_watchers_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "user_id", name="uq_task_watchers_task_id_user_id"),
    )
    with op.batch_alter_table("task_watchers", schema=None) as batch_op:
        batch_op.create_index("ix_task_watchers_user_id", ["user_id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("comment_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(*_KINDS, name="notification_kind", native_enum=False),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "actor_id IS NULL OR actor_id <> recipient_id", name="ck_notifications_not_self"
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name="fk_notifications_actor_id_users", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["comment_id"],
            ["task_comments.id"],
            name="fk_notifications_comment_id_task_comments",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["users.id"],
            name="fk_notifications_recipient_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name="fk_notifications_task_id_tasks", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_notifications_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.create_index("ix_notifications_comment_id", ["comment_id"], unique=False)
        batch_op.create_index(
            "ix_notifications_recipient_id_read_at_created_at",
            ["recipient_id", "read_at", "created_at"],
            unique=False,
        )
        batch_op.create_index("ix_notifications_task_id", ["task_id"], unique=False)
        batch_op.create_index("ix_notifications_workspace_id", ["workspace_id"], unique=False)

    _backfill_watchers()


def downgrade() -> None:
    """Downgrade schema. Loses every watcher and notification."""
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.drop_index("ix_notifications_workspace_id")
        batch_op.drop_index("ix_notifications_task_id")
        batch_op.drop_index("ix_notifications_recipient_id_read_at_created_at")
        batch_op.drop_index("ix_notifications_comment_id")

    op.drop_table("notifications")
    with op.batch_alter_table("task_watchers", schema=None) as batch_op:
        batch_op.drop_index("ix_task_watchers_user_id")

    op.drop_table("task_watchers")


def _backfill_watchers() -> None:
    """Creators, assignees and commenters of existing tasks, if still members."""
    bind = op.get_bind()
    candidates = sa.union(
        sa.select(_tasks.c.id.label("task_id"), _tasks.c.owner_id.label("candidate")),
        sa.select(_tasks.c.id, _tasks.c.assignee_id).where(_tasks.c.assignee_id.is_not(None)),
        sa.select(_comments.c.task_id, _comments.c.author_id).where(
            _comments.c.author_id.is_not(None)
        ),
    ).subquery()
    rows = bind.execute(
        sa.select(candidates.c.task_id, candidates.c.candidate)
        .join(_tasks, _tasks.c.id == candidates.c.task_id)
        .where(
            sa.exists(
                sa.select(sa.literal(1))
                .select_from(_members)
                .where(
                    _members.c.workspace_id == _tasks.c.workspace_id,
                    _members.c.user_id == candidates.c.candidate,
                )
            )
        )
        .distinct()
    ).all()

    now = datetime.now(UTC)
    if rows:
        op.bulk_insert(
            _watchers,
            [
                {"id": uuid.uuid4(), "task_id": task_id, "user_id": user_id, "created_at": now}
                for task_id, user_id in rows
            ],
        )
