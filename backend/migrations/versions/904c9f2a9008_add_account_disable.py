"""add account disable

Gives platform operators a way to stop an individual account: ``disabled_at``
blocks sign-in and every session, and ``disabled_reason`` is the operator's
record. This is the lever for a person; a private workspace is never suspended.

Both columns are nullable and start empty, so every existing account stays
active and no backfill is needed.

Revision ID: 904c9f2a9008
Revises: dea55f1af32c
Create Date: 2026-11-05

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "904c9f2a9008"
down_revision: str | Sequence[str] | None = "dea55f1af32c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("disabled_reason", sa.Text(), nullable=True))
        batch_op.create_check_constraint(
            "ck_users_disabled_reason_bounded",
            "disabled_reason IS NULL OR length(disabled_reason) <= 500",
        )


def downgrade() -> None:
    """Downgrade schema.

    Disabled accounts become usable again: the previous schema has no way to
    express "stopped". Re-disable them after upgrading if this is rolled back.
    """
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint("ck_users_disabled_reason_bounded", type_="check")
        batch_op.drop_column("disabled_reason")
        batch_op.drop_column("disabled_at")
