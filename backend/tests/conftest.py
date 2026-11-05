"""Shared fixtures.

Every test gets an isolated temporary SQLite database and only synthetic
fixtures with reserved-for-documentation ``example.com`` addresses; tests never
depend on the developer's environment or external services (architecture doc
sections 9.1 and 10.1).
"""

import itertools
import uuid
from collections.abc import Callable, Generator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import Base, build_engine, get_db
from app.main import create_app
from app.modules.auth.cookies import CSRF_HEADER_NAME, CSRF_HEADER_VALUE
from app.modules.users.enums import PlatformRole
from app.modules.users.models import User
from tests.synth import BASE, PASSWORD


@pytest.fixture()
def engine(tmp_path: Any) -> Generator[Engine, None, None]:
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
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
def app(session: Session) -> Generator[FastAPI, None, None]:
    application = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        yield session

    application.dependency_overrides[get_db] = override_get_db
    yield application
    application.dependency_overrides.clear()


@pytest.fixture()
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    """Browser-like client that carries the CSRF header and a cookie jar."""
    with TestClient(app, headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE}) as test_client:
        yield test_client


@pytest.fixture()
def unguarded_client(app: FastAPI) -> Generator[TestClient, None, None]:
    """Client that never sends the CSRF header, like a cross-site form post."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def second_client(app: FastAPI) -> Generator[TestClient, None, None]:
    """A second browser session, with its own cookie jar, on the same database.

    Use this for every second identity in a test. ``client``, ``authed_client``
    and ``operator_client`` all wrap the *same* instance, so signing in on
    ``client`` replaces the session those fixtures established --- which fails
    quietly as a wrong-role 403 rather than loudly as a broken session.
    """
    with TestClient(app, headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE}) as test_client:
        yield test_client


@pytest.fixture()
def sign_in(session: Session) -> Callable[..., dict[str, Any]]:
    """Register and log in a synthetic account, leaving its cookies in place.

    Returns the public user payload. Passing
    ``platform_role=PlatformRole.OPERATOR`` promotes the account *after* login,
    which also proves the role is read from the database rather than from the
    access token.
    """
    counter = itertools.count(1)

    def _sign_in(
        client: TestClient,
        *,
        email: str | None = None,
        password: str = PASSWORD,
        platform_role: PlatformRole = PlatformRole.USER,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        address = email or f"member{next(counter)}@example.com"
        payload: dict[str, Any] = {"email": address, "password": password}
        if display_name is not None:
            payload["display_name"] = display_name

        registered = client.post(f"{BASE}/auth/register", json=payload)
        assert registered.status_code == 201, registered.text
        user = registered.json()

        logged_in = client.post(f"{BASE}/auth/login", json=payload)
        assert logged_in.status_code == 200, logged_in.text

        if platform_role is not PlatformRole.USER:
            row = session.get(User, uuid.UUID(user["id"]))
            assert row is not None
            row.platform_role = platform_role
            session.commit()

        return user

    return _sign_in


@pytest.fixture()
def authed_client(client: TestClient, sign_in: Callable[..., dict[str, Any]]) -> TestClient:
    """``client`` with a member session already established."""
    sign_in(client)
    return client


@pytest.fixture()
def operator_client(client: TestClient, sign_in: Callable[..., dict[str, Any]]) -> TestClient:
    """``client`` with an established platform operator session."""
    sign_in(client, platform_role=PlatformRole.OPERATOR)
    return client


@pytest.fixture()
def make_task(authed_client: TestClient) -> Callable[..., dict[str, Any]]:
    """Create a synthetic task as the signed-in user and return its JSON body."""

    def _make(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {"title": "Synthetic task", **overrides}
        response = authed_client.post(f"{BASE}/tasks", json=payload)
        assert response.status_code == 201, response.text
        return response.json()

    return _make


@pytest.fixture()
def create_team() -> Callable[..., dict[str, Any]]:
    """Open a company tenant through the API and return its JSON body."""
    counter = itertools.count(1)

    def _create(
        client: TestClient, *, name: str | None = None, slug: str | None = None
    ) -> dict[str, Any]:
        index = next(counter)
        payload = {
            "name": name or f"Synthetic Co {index}",
            "slug": slug or f"synthetic-co-{index}",
        }
        response = client.post(f"{BASE}/workspaces", json=payload)
        assert response.status_code == 201, response.text
        return response.json()

    return _create


@pytest.fixture()
def team(authed_client: TestClient, create_team: Callable[..., dict[str, Any]]) -> dict[str, Any]:
    """A company owned by the ``authed_client``'s account."""
    return create_team(authed_client)
