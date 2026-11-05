"""SQLAlchemy engine, session factory and declarative base.

One session is created per request via ``get_db`` and never shared across
concurrent requests (architecture doc section 6.2).
"""

import sqlite3
from collections.abc import Generator
from typing import cast

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base shared by all module models."""


def build_engine(database_url: str) -> Engine:
    """Create an engine with this project's connection rules.

    Shared with the test suite, so the SQLite sandbox enforces the same
    integrity rules as the canonical PostgreSQL target.
    """
    kwargs: dict[str, object] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        # SQLite sessions are used per-request across threads by uvicorn.
        kwargs["connect_args"] = {"check_same_thread": False}

    engine = create_engine(database_url, **kwargs)

    if engine.dialect.name == "sqlite":
        # SQLite switches foreign keys off per connection. Leaving them off
        # would accept orphan rows that PostgreSQL would refuse, so
        # referential integrity is enabled on every connection (section 6).
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)

    return engine


def _enable_sqlite_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
    """The DBAPI connection handed to SQLAlchemy's ``connect`` event."""
    cursor = cast(sqlite3.Connection, dbapi_connection).cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


engine: Engine = build_engine(get_settings().database_url)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields one database session per request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
