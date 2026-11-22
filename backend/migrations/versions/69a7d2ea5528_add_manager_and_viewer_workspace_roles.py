"""add manager and viewer workspace roles

Widens the workspace role vocabulary from ``owner``, ``admin``, ``member`` to
``owner``, ``admin``, ``manager``, ``member``, ``viewer``, in the two columns that
store one:

* ``workspace_members.role`` --- what a person is in a tenant;
* ``workspace_invites.role`` --- what an open offer would make them.

Both are non-native enums, i.e. ``VARCHAR`` sized to the longest value. That was
``member`` (6), and ``manager`` needs 7, so each column is widened; SQLite ignores
the length, PostgreSQL would otherwise refuse the first manager. No row changes:
every existing value keeps its meaning, and ``member`` keeps exactly the rights it
had to the work it created or holds.

Downgrading narrows the columns back, so the two new values have to go first.
Both become ``member``, the only older role that can still work: for a manager
that takes authority away, and for a viewer it *adds* the right to contribute ---
the older schema simply has no read-only role. Review viewers before downgrading
a database that has any.

Revision ID: 69a7d2ea5528
Revises: 1ab143f1f033
Create Date: 2026-11-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "69a7d2ea5528"
down_revision: str | Sequence[str] | None = "1ab143f1f033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The role vocabularies, spelled out rather than imported from the application:
# a migration must keep working after the enums evolve (architecture doc section 6).
_ROLES_BEFORE = ("owner", "admin", "member")
_ROLES_AFTER = ("owner", "admin", "manager", "member", "viewer")
_NEW_ROLES = ("manager", "viewer")
_FALLBACK_ROLE = "member"

_TABLES = ("workspace_members", "workspace_invites")


def _workspace_role(values: Sequence[str]) -> sa.Enum:
    """The role column, stored as values exactly as the models declare it."""
    return sa.Enum(*values, name="workspace_role", native_enum=False)


def upgrade() -> None:
    """Upgrade schema."""
    for table in _TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(
                "role",
                existing_type=_workspace_role(_ROLES_BEFORE),
                type_=_workspace_role(_ROLES_AFTER),
                existing_nullable=False,
            )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    for table in _TABLES:
        rows = sa.table(table, sa.column("role", sa.String()))
        bind.execute(rows.update().where(rows.c.role.in_(_NEW_ROLES)).values(role=_FALLBACK_ROLE))
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(
                "role",
                existing_type=_workspace_role(_ROLES_AFTER),
                type_=_workspace_role(_ROLES_BEFORE),
                existing_nullable=False,
            )
