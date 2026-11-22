"""add automation settings

One new table, so nothing existing is touched:

* ``automation_settings`` --- whether a workspace has switched one catalogue
  automation rule on, and who last switched it. One row per workspace per rule
  (``uq_automation_settings_workspace_id_rule``, whose leading column also serves
  "this workspace's rules"), written the first time a rule is switched: a rule
  without a row is off, so every existing workspace starts with every rule off and
  nothing needs backfilling. Deleting the workspace deletes its rows; the person
  who last switched a rule is ``SET NULL``.

The ``completed`` notification kind is a new value in the existing
``notifications.kind`` string column, which already fits it.

Revision ID: 6f27586ca160
Revises: 69a7d2ea5528
Create Date: 2026-11-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6f27586ca160"
down_revision: str | Sequence[str] | None = "69a7d2ea5528"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Spelled out rather than imported from the application: a migration must keep
# working after the enums evolve (architecture doc section 6).
_RULES = ("notify_creator_on_done", "notify_watchers_on_done", "notify_owners_on_done")

_notifications = sa.table("notifications", sa.column("kind", sa.String()))


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "automation_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column(
            "rule",
            sa.Enum(*_RULES, name="automation_rule", native_enum=False, length=64),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name="fk_automation_settings_updated_by_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_automation_settings_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id", "rule", name="uq_automation_settings_workspace_id_rule"
        ),
    )


def downgrade() -> None:
    """Downgrade schema. Loses every automation setting, and the notifications the
    rules sent --- the older code cannot read a ``completed`` notification."""
    op.get_bind().execute(_notifications.delete().where(_notifications.c.kind == "completed"))
    op.drop_table("automation_settings")
