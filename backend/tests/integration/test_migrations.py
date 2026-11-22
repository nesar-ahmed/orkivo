"""Integration tests for the migration chain (architecture doc section 6).

The rest of the suite builds its schema with ``create_all``, which says nothing
about the migrations a real database runs. These run the real chain, through
Alembic, against a throwaway SQLite file: it must build exactly the schema the
models describe, every step must be undoable, and a migration that rewrites data
must keep what it promises to keep.
"""

import uuid
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from app.core.config import get_settings
from app.core.db import Base, build_engine
from app.shared.time import utc_now

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parents[2]

#: The revision that added the manager and viewer roles, and the one before it.
ROLES_REVISION = "69a7d2ea5528"
BEFORE_ROLES = "1ab143f1f033"


# The tables the data test writes, declared with just the columns it fills, the way
# the migrations themselves declare them: typed, so values are stored exactly as the
# application stores them, and independent of today's models.
def _stamps() -> tuple[sa.ColumnClause[Any], ...]:
    """Fresh timestamp columns: a column can belong to one table only."""
    return (
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )


WORKSPACES = sa.table(
    "workspaces",
    sa.column("id", sa.Uuid()),
    sa.column("kind", sa.String()),
    sa.column("name", sa.String()),
    sa.column("slug", sa.String()),
    sa.column("status", sa.String()),
    *_stamps(),
)
USERS = sa.table(
    "users",
    sa.column("id", sa.Uuid()),
    sa.column("email", sa.String()),
    sa.column("password_hash", sa.String()),
    sa.column("display_name", sa.String()),
    sa.column("platform_role", sa.String()),
    *_stamps(),
)
MEMBERS = sa.table(
    "workspace_members",
    sa.column("id", sa.Uuid()),
    sa.column("workspace_id", sa.Uuid()),
    sa.column("user_id", sa.Uuid()),
    sa.column("role", sa.String()),
    sa.column("joined_at", sa.DateTime(timezone=True)),
    *_stamps(),
)


@pytest.fixture()
def database(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Generator[tuple[Config, sa.Engine]]:
    """An Alembic configuration aimed at an empty database file, and an engine on it.

    ``migrations/env.py`` reads the URL from the application settings, so the
    environment is pointed at the file and the cached settings are dropped ---
    before the test, and again after, so no other test sees this URL.
    """
    url = f"sqlite:///{tmp_path / 'migrations.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    config = Config()  # No ini file: the test run's logging is left alone.
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    engine = build_engine(url)
    yield config, engine
    engine.dispose()
    get_settings.cache_clear()


def test_the_chain_builds_exactly_the_schema_the_models_describe(
    database: tuple[Config, sa.Engine],
) -> None:
    config, engine = database

    command.upgrade(config, "head")

    with engine.connect() as connection:
        drift = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert drift == []


def test_every_migration_can_be_undone_and_redone(database: tuple[Config, sa.Engine]) -> None:
    config, engine = database
    head = ScriptDirectory.from_config(config).get_current_head()

    command.upgrade(config, "head")
    command.downgrade(config, "base")
    with engine.connect() as connection:
        assert set(sa.inspect(connection).get_table_names()) == {"alembic_version"}

    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == head


def test_the_role_migration_keeps_members_and_folds_new_roles_back(
    database: tuple[Config, sa.Engine],
) -> None:
    """Existing roles survive the widening untouched; undoing it turns the two new
    roles into ``member``, the only older role that can still work."""
    config, engine = database
    command.upgrade(config, ROLES_REVISION)
    roles = {"owner": uuid.uuid4(), "manager": uuid.uuid4(), "viewer": uuid.uuid4()}
    workspace_id = uuid.uuid4()
    now = utc_now()
    with engine.begin() as connection:
        connection.execute(
            WORKSPACES.insert().values(
                id=workspace_id,
                kind="team",
                name="Synthetic Co",
                slug="synthetic-co",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        for role, user_id in roles.items():
            connection.execute(
                USERS.insert().values(
                    id=user_id,
                    email=f"{role}@example.com",
                    password_hash="not-a-real-hash",
                    display_name=role,
                    platform_role="user",
                    created_at=now,
                    updated_at=now,
                )
            )
            connection.execute(
                MEMBERS.insert().values(
                    id=uuid.uuid4(),
                    workspace_id=workspace_id,
                    user_id=user_id,
                    role=role,
                    joined_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )

    command.downgrade(config, BEFORE_ROLES)

    with engine.connect() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT users.email, workspace_members.role FROM workspace_members "
                "JOIN users ON users.id = workspace_members.user_id ORDER BY users.email"
            )
        ).all()
    assert [tuple(row) for row in rows] == [
        ("manager@example.com", "member"),
        ("owner@example.com", "owner"),
        ("viewer@example.com", "member"),
    ]
