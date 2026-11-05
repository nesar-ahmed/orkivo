"""add auth sessions, users and task ownership

Creates the ``users`` and ``sessions`` tables and makes ``tasks`` owned by a
user. Ownership is added in three steps --- nullable column, backfill, then
``NOT NULL`` plus the foreign key --- so a database that already holds tasks is
never left with rows that fail the new invariant.

Revision ID: 9a922647cb7d
Revises: 1e60773d8e31
Create Date: 2026-11-04 19:24:17.246959
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9a922647cb7d"
down_revision: str | Sequence[str] | None = "1e60773d8e31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tasks written before authentication existed are assigned to this synthetic
# bootstrap account, so ``owner_id`` can be a required column rather than a
# nullable "owned by nobody" loophole. The address uses a domain reserved for
# documentation by RFC 2606, so it can never reach a real mailbox
# (architecture doc section 9.1).
LEGACY_OWNER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
LEGACY_OWNER_EMAIL = "legacy-owner@example.com"
LEGACY_OWNER_DISPLAY_NAME = "Legacy Owner"
# Not a credential: this account cannot sign in. A placeholder for the Argon2id
# format, with no known plaintext.
LEGACY_OWNER_HASH_PREFIX = "!not-a-real-credential-argon2id-placeholder"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column(
            "role",
            sa.Enum("member", "admin", name="user_role", native_enum=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(display_name) > 0", name="ck_users_display_name_not_empty"),
        sa.CheckConstraint("length(email) > 0", name="ck_users_email_not_empty"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_users_email"), ["email"], unique=True)
        batch_op.create_index(batch_op.f("ix_users_role"), ["role"], unique=False)

    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_sessions_users_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_sessions_family_id"), ["family_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_sessions_token_hash"), ["token_hash"], unique=True)
        batch_op.create_index(batch_op.f("ix_sessions_user_id"), ["user_id"], unique=False)

    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("owner_id", sa.Uuid(), nullable=True))

    _assign_existing_tasks_to_legacy_owner()

    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.alter_column("owner_id", existing_type=sa.Uuid(), nullable=False)
        batch_op.create_index(batch_op.f("ix_tasks_owner_id"), ["owner_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_tasks_owner_id_users",
            "users",
            ["owner_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_constraint("fk_tasks_owner_id_users", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_tasks_owner_id"))
        batch_op.drop_column("owner_id")

    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_sessions_user_id"))
        batch_op.drop_index(batch_op.f("ix_sessions_token_hash"))
        batch_op.drop_index(batch_op.f("ix_sessions_family_id"))

    op.drop_table("sessions")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_role"))
        batch_op.drop_index(batch_op.f("ix_users_email"))

    op.drop_table("users")


def _assign_existing_tasks_to_legacy_owner() -> None:
    """Give pre-authentication tasks an owner, only when such rows exist."""
    existing_tasks = op.get_bind().execute(sa.text("SELECT COUNT(*) FROM tasks")).scalar()
    if not existing_tasks:
        return

    now = datetime.now(UTC)
    users = sa.table(
        "users",
        sa.column("id", sa.Uuid),
        sa.column("email", sa.String),
        # Bound as a plain string: ``user_role`` is a non-native enum, so the
        # column is VARCHAR and needs no Python enum member here.
        sa.column("role", sa.String),
        sa.column("password_hash", sa.String),
        sa.column("display_name", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        users,
        [
            {
                "id": LEGACY_OWNER_ID,
                "email": LEGACY_OWNER_EMAIL,
                "role": "member",
                "password_hash": f"{LEGACY_OWNER_HASH_PREFIX}:{LEGACY_OWNER_ID}",
                "display_name": LEGACY_OWNER_DISPLAY_NAME,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    op.execute(
        sa.text("UPDATE tasks SET owner_id = :owner_id WHERE owner_id IS NULL").bindparams(
            sa.bindparam("owner_id", type_=sa.Uuid(), value=LEGACY_OWNER_ID)
        )
    )
