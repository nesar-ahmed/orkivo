"""SQLAlchemy engine, session factory and declarative base.

One session is created per request via ``get_db`` and never shared across
concurrent requests (architecture doc section 6.2).
"""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base shared by all module models."""


def _build_engine(database_url: str) -> Engine:
    kwargs: dict[str, object] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        # SQLite sessions are used per-request across threads by uvicorn.
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(database_url, **kwargs)


engine: Engine = _build_engine(get_settings().database_url)

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
