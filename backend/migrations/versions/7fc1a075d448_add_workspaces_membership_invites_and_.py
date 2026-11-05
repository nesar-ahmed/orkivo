"""add workspaces, membership, invitations and platform roles

Tenancy arrives in three moves, each of them reversible:

1. The ``workspaces`` / ``workspace_members`` / ``workspace_invites`` tables.
2. ``users.role`` becomes ``users.platform_role``, and its values become ``user``
   and ``operator``. That column has always described standing on the *platform*
   --- it decided who could read the account directory --- and never a company.
   Renaming it is what lets ``workspace_members.role`` exist without two things
   called "role" meaning different things.
3. Every existing account is given the private workspace that registration now
   creates, so the next revision can make "work belongs to a tenant" a required
   column instead of a nullable one nobody fills in.

Revision ID: 7fc1a075d448
Revises: 9a922647cb7d
Create Date: 2026-11-04

"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7fc1a075d448"
down_revision: str | Sequence[str] | None = "9a922647cb7d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The two role vocabularies, spelled out rather than imported from the
# application: a migration must keep working after the enums evolve
# (architecture doc section 6).
_LEGACY_TO_PLATFORM = {"member": "user", "admin": "operator"}
_PLATFORM_TO_LEGACY = {value: key for key, value in _LEGACY_TO_PLATFORM.items()}

# Tables used only for the data steps below, declared with the columns this
# revision touches. ``sa.Uuid`` matters: it formats identifiers the same way the
# application's models do, so backfilled rows are indistinguishable from rows
# created through the API.
_users = sa.table(
    "users",
    sa.column("id", sa.Uuid()),
    sa.column("display_name", sa.String()),
    sa.column("platform_role", sa.String()),
    sa.column("role", sa.String()),
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

_PERSONAL_NAME_SUFFIX = "'s workspace"


def _workspace_role() -> sa.Enum:
    """The role column, stored as values exactly as the models declare it."""
    return sa.Enum("owner", "admin", "member", name="workspace_role", native_enum=False)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("personal", "team", name="workspace_kind", native_enum=False),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=63), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "suspended", name="workspace_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("operator_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(name) > 0", name="ck_workspaces_name_not_empty"),
        sa.CheckConstraint("length(name) <= 120", name="ck_workspaces_name_not_too_long"),
        sa.CheckConstraint(
            "(kind = 'team' AND slug IS NOT NULL) OR (kind = 'personal' AND slug IS NULL)",
            name="ck_workspaces_slug_matches_kind",
        ),
        sa.CheckConstraint(
            "operator_note IS NULL OR length(operator_note) <= 500",
            name="ck_workspaces_operator_note_bounded",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workspaces_kind"), "workspaces", ["kind"], unique=False)
    # A slug is both an address and a lookup: one unique index covers both, and
    # NULL slugs (personal tenants) stay distinct from each other.
    op.create_index(op.f("ix_workspaces_slug"), "workspaces", ["slug"], unique=True)
    op.create_index(op.f("ix_workspaces_status"), "workspaces", ["status"], unique=False)

    op.create_table(
        "workspace_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", _workspace_role(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_workspace_members_workspace",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_workspace_members_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_workspace_user"),
    )
    op.create_index(
        op.f("ix_workspace_members_user_id"), "workspace_members", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_workspace_members_workspace_id"),
        "workspace_members",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "workspace_invites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("role", _workspace_role(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "accepted",
                "declined",
                "revoked",
                name="invite_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("invited_by", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(email) > 0", name="ck_workspace_invites_email_not_empty"),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_workspace_invites_workspace",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by"],
            ["users.id"],
            name="fk_workspace_invites_inviter",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "email", name="uq_workspace_invites_workspace_email"),
    )
    op.create_index(
        op.f("ix_workspace_invites_email"), "workspace_invites", ["email"], unique=False
    )
    op.create_index(
        op.f("ix_workspace_invites_status"), "workspace_invites", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_workspace_invites_workspace_id"),
        "workspace_invites",
        ["workspace_id"],
        unique=False,
    )

    # --- users.role -> users.platform_role ---------------------------------
    # Renamed, retyped and then re-valued. The retyping is not decoration: the
    # old column was VARCHAR(6) ("member"), and "operator" is eight characters,
    # so a rename that kept the type would store a truncated role on every
    # database that actually enforces column length.
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "role",
            new_column_name="platform_role",
            type_=sa.Enum("user", "operator", name="platform_role", native_enum=False),
            existing_type=sa.Enum("member", "admin", name="user_role", native_enum=False),
            existing_nullable=False,
        )

    bind = op.get_bind()
    for legacy, platform in _LEGACY_TO_PLATFORM.items():
        bind.execute(
            _users.update().where(_users.c.platform_role == legacy).values(platform_role=platform)
        )

    # The index keeps the column's name, or it silently indexes nothing.
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_role")
        batch_op.create_index("ix_users_platform_role", ["platform_role"], unique=False)

    _backfill_personal_workspaces()


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()

    # Tenancy rows go first: they reference ``users`` and must not outlive it.
    bind.execute(_workspace_members.delete())
    bind.execute(_workspaces.delete())

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_platform_role")
        batch_op.create_index("ix_users_role", ["platform_role"], unique=False)

    for platform, legacy in _PLATFORM_TO_LEGACY.items():
        bind.execute(
            _users.update().where(_users.c.platform_role == platform).values(platform_role=legacy)
        )

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "platform_role",
            new_column_name="role",
            existing_type=sa.Enum("member", "admin", name="user_role", native_enum=False),
            existing_nullable=False,
        )

    op.drop_index(op.f("ix_workspace_invites_workspace_id"), table_name="workspace_invites")
    op.drop_index(op.f("ix_workspace_invites_status"), table_name="workspace_invites")
    op.drop_index(op.f("ix_workspace_invites_email"), table_name="workspace_invites")
    op.drop_table("workspace_invites")
    op.drop_index(op.f("ix_workspace_members_workspace_id"), table_name="workspace_members")
    op.drop_index(op.f("ix_workspace_members_user_id"), table_name="workspace_members")
    op.drop_table("workspace_members")
    op.drop_index(op.f("ix_workspaces_status"), table_name="workspaces")
    op.drop_index(op.f("ix_workspaces_slug"), table_name="workspaces")
    op.drop_index(op.f("ix_workspaces_kind"), table_name="workspaces")
    op.drop_table("workspaces")


def _backfill_personal_workspaces() -> None:
    """Give every existing account the private tenant registration now creates.

    Written one row at a time through Core, using the same ``sa.Uuid`` formatting
    the application uses, so a backfilled workspace is byte-identical to a
    registered one. The personal name mirrors ``WorkspaceService`` exactly: a
    drift here would show up as a different name for the same account depending
    on when it signed up.
    """
    bind = op.get_bind()
    now = datetime.now(UTC)
    accounts = bind.execute(
        sa.select(_users.c.id, _users.c.display_name).order_by(_users.c.id)
    ).all()

    for user_id, display_name in accounts:
        existing = bind.execute(
            sa.select(sa.literal(1))
            .select_from(_workspaces)
            .join(
                _workspace_members,
                _workspace_members.c.workspace_id == _workspaces.c.id,
            )
            .where(
                _workspace_members.c.user_id == user_id,
                _workspaces.c.kind == "personal",
            )
        ).first()
        if existing is not None:
            continue

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
