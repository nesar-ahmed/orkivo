"""scope tasks to workspaces

Moves the authorization boundary for tasks from "who created it" to "which tenant
holds it", so a company can share work among its members. Done in three steps ---
nullable column, backfill, then ``NOT NULL`` plus the foreign key and index --- so
a database that already holds tasks is never left with rows that break the new
invariant.

Every existing task is placed in its creator's *personal* workspace. That keeps
the upgrade privacy-neutral: nothing anyone wrote before this revision becomes
visible to a single extra person. Sharing starts with tasks created in a company
afterwards.

Revision ID: dea55f1af32c
Revises: 7fc1a075d448
Create Date: 2026-11-05

"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dea55f1af32c"
down_revision: str | Sequence[str] | None = "7fc1a075d448"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Declared with just the columns this revision touches, and with ``sa.Uuid`` so
# identifiers are written exactly as the application writes them.
_tasks = sa.table(
    "tasks",
    sa.column("id", sa.Uuid()),
    sa.column("owner_id", sa.Uuid()),
    sa.column("workspace_id", sa.Uuid()),
)
_users = sa.table(
    "users",
    sa.column("id", sa.Uuid()),
    sa.column("display_name", sa.String()),
)
_workspaces = sa.table(
    "workspaces",
    sa.column("id", sa.Uuid()),
    sa.column("kind", sa.String()),
    sa.column("name", sa.String()),
    sa.column("slug", sa.String()),
    sa.column("status", sa.String()),
    sa.column("operator_note", sa.Text()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
_workspace_members = sa.table(
    "workspace_members",
    sa.column("id", sa.Uuid()),
    sa.column("workspace_id", sa.Uuid()),
    sa.column("user_id", sa.Uuid()),
    sa.column("role", sa.String()),
    sa.column("joined_at", sa.DateTime(timezone=True)),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

# Mirrors ``WorkspaceService.create_personal_for`` and revision 7fc1a075d448.
_PERSONAL_NAME_SUFFIX = "'s workspace"


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("workspace_id", sa.Uuid(), nullable=True))

    _assign_tasks_to_personal_workspaces()

    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.alter_column("workspace_id", existing_type=sa.Uuid(), nullable=False)
        batch_op.create_index(
            "ix_tasks_workspace_id_created_at", ["workspace_id", "created_at"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_tasks_workspace_id_workspaces",
            "workspaces",
            ["workspace_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    """Downgrade schema.

    Lossless for personal work. Tasks that were created inside a company keep
    their creator in ``owner_id``, so after a downgrade they become that person's
    private tasks again --- the only scope the previous schema can express.
    """
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_constraint("fk_tasks_workspace_id_workspaces", type_="foreignkey")
        batch_op.drop_index("ix_tasks_workspace_id_created_at")
        batch_op.drop_column("workspace_id")


def _personal_workspace_of(owner_id: sa.ColumnElement[uuid.UUID]) -> sa.ScalarSelect[uuid.UUID]:
    """The personal workspace an account is a member of, as a scalar subquery."""
    return (
        sa.select(_workspaces.c.id)
        .join(_workspace_members, _workspace_members.c.workspace_id == _workspaces.c.id)
        .where(_workspace_members.c.user_id == owner_id, _workspaces.c.kind == "personal")
        .order_by(_workspaces.c.created_at, _workspaces.c.id)
        .limit(1)
        .scalar_subquery()
    )


def _assign_tasks_to_personal_workspaces() -> None:
    """Put every task in its creator's private tenant.

    Registration and revision 7fc1a075d448 give every account a personal
    workspace, so the repair step below should find nothing to do. It exists so
    that a database edited by hand cannot make this upgrade fail halfway.
    """
    bind = op.get_bind()
    _create_missing_personal_workspaces()
    bind.execute(
        _tasks.update()
        .where(_tasks.c.workspace_id.is_(None))
        .values(workspace_id=_personal_workspace_of(_tasks.c.owner_id))
    )


def _create_missing_personal_workspaces() -> None:
    bind = op.get_bind()
    orphaned_owners = bind.execute(
        sa.select(_users.c.id, _users.c.display_name)
        .where(
            _users.c.id.in_(sa.select(_tasks.c.owner_id).distinct()),
            ~sa.exists(
                sa.select(sa.literal(1))
                .select_from(_workspaces)
                .join(_workspace_members, _workspace_members.c.workspace_id == _workspaces.c.id)
                .where(
                    _workspace_members.c.user_id == _users.c.id,
                    _workspaces.c.kind == "personal",
                )
            ),
        )
        .order_by(_users.c.id)
    ).all()

    now = datetime.now(UTC)
    for user_id, display_name in orphaned_owners:
        workspace_id = uuid.uuid4()
        bind.execute(
            _workspaces.insert().values(
                id=workspace_id,
                kind="personal",
                name=f"{display_name}{_PERSONAL_NAME_SUFFIX}",
                slug=None,
                status="active",
                operator_note=None,
                created_at=now,
                updated_at=now,
            )
        )
        bind.execute(
            _workspace_members.insert().values(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                user_id=user_id,
                role="owner",
                joined_at=now,
                created_at=now,
                updated_at=now,
            )
        )
