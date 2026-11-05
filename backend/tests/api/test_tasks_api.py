"""API tests: HTTP status codes, validation, and response contracts.

The tasks API is authenticated, so these run against a client that already
holds a session; authorization itself is covered in
``test_tasks_authorization.py``.
"""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.api

BASE = "/api/v1"

MakeTask = Callable[..., dict[str, Any]]


def test_health_reports_database_ok(client: TestClient) -> None:
    """The readiness probe stays public: no session is required to check health."""
    response = client.get(f"{BASE}/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_create_task_returns_201_and_public_shape(authed_client: TestClient) -> None:
    response = authed_client.post(
        f"{BASE}/tasks",
        json={"title": "Ship baseline", "priority": "high", "due_date": "2026-12-01"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Ship baseline"
    assert body["status"] == "todo"
    assert body["priority"] == "high"
    assert body["due_date"] == "2026-12-01"
    assert uuid.UUID(body["id"])  # UUID primary key exposed
    assert "created_at" in body and "updated_at" in body
    # Ownership is an internal detail: it is never part of the contract.
    assert "owner_id" not in body


def test_create_task_rejects_blank_title_with_consistent_error(authed_client: TestClient) -> None:
    response = authed_client.post(f"{BASE}/tasks", json={"title": "   "})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert any(detail["field"] == "title" for detail in error["details"])


def test_create_task_rejects_unknown_enum(authed_client: TestClient) -> None:
    response = authed_client.post(f"{BASE}/tasks", json={"title": "x", "status": "archived"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_task_returns_404_contract(authed_client: TestClient) -> None:
    response = authed_client.get(f"{BASE}/tasks/{uuid.uuid4()}")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "TASK_NOT_FOUND"
    assert error["message"] == "The requested task was not found."


def test_list_tasks_pagination_contract(authed_client: TestClient, make_task: MakeTask) -> None:
    for index in range(3):
        make_task(title=f"Task {index}")

    response = authed_client.get(f"{BASE}/tasks?page=1&page_size=2")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["pages"] == 2
    assert len(body["items"]) == 2


def test_list_tasks_rejects_oversized_page(authed_client: TestClient) -> None:
    response = authed_client.get(f"{BASE}/tasks?page_size=500")

    assert response.status_code == 422


def test_update_task_moves_status(authed_client: TestClient, make_task: MakeTask) -> None:
    task = make_task(title="Move me")

    response = authed_client.patch(f"{BASE}/tasks/{task['id']}", json={"status": "in_progress"})

    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


def test_delete_task_returns_204_and_removes(
    authed_client: TestClient, make_task: MakeTask
) -> None:
    task = make_task(title="Delete me")

    response = authed_client.delete(f"{BASE}/tasks/{task['id']}")

    assert response.status_code == 204
    assert authed_client.get(f"{BASE}/tasks/{task['id']}").status_code == 404


def test_unknown_route_uses_consistent_error_shape(client: TestClient) -> None:
    response = client.get(f"{BASE}/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
