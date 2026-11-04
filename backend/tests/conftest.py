"""Shared fixtures.

Every test gets an isolated temporary SQLite database; tests never depend on
the developer's environment or external services (architecture doc 10.1).
"""

from collections.abc import Callable, Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import Base, get_db
from app.main import create_app


@pytest.fixture()
def engine(tmp_path: Any) -> Generator[Engine, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def session(engine: Engine) -> Generator[Session, None, None]:
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    yield session
    session.close()


@pytest.fixture()
def client(session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def make_task(client: TestClient) -> Callable[..., dict[str, Any]]:
    """Create a synthetic task through the API and return its JSON body."""

    def _make(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {"title": "Synthetic task", **overrides}
        response = client.post("/api/v1/tasks", json=payload)
        assert response.status_code == 201, response.text
        return response.json()

    return _make
