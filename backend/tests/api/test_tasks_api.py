"""API tests: HTTP status codes, validation, and response contracts."""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.api

BASE = "/api/v1"

MakeTask = Callable[..., dict[str, Any]]


def test_health_reports_database_ok(client: TestClient) -> None:
    response = client.get(f"{BASE}/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_create_task_returns_201_and_public_shape(client: TestClient) -> None:
    response = client.post(
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


def test_create_task_rejects_blank_title_with_consistent_error(client: TestClient) -> None:
    response = client.post(f"{BASE}/tasks", json={"title": "   "})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert any(detail["field"] == "title" for detail in error["details"])


def test_create_task_rejects_unknown_enum(client: TestClient) -> None:
    response = client.post(f"{BASE}/tasks", json={"title": "x", "status": "archived"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_task_returns_404_contract(client: TestClient) -> None:
    response = client.get(f"{BASE}/tasks/{uuid.uuid4()}")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "TASK_NOT_FOUND"
    assert error["message"] == "The requested task was not found."


def test_list_tasks_pagination_contract(client: TestClient, make_task: MakeTask) -> None:
    for index in range(3):
        make_task(title=f"Task {index}")

    response = client.get(f"{BASE}/tasks?page=1&page_size=2")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["pages"] == 2
    assert len(body["items"]) == 2


def test_list_tasks_rejects_oversized_page(client: TestClient) -> None:
    response = client.get(f"{BASE}/tasks?page_size=500")

    assert response.status_code == 422


def test_update_task_moves_status(client: TestClient, make_task: MakeTask) -> None:
    task = make_task(title="Move me")

    response = client.patch(f"{BASE}/tasks/{task['id']}", json={"status": "in_progress"})

    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


def test_delete_task_returns_204_and_removes(client: TestClient, make_task: MakeTask) -> None:
    task = make_task(title="Delete me")

    response = client.delete(f"{BASE}/tasks/{task['id']}")

    assert response.status_code == 204
    assert client.get(f"{BASE}/tasks/{task['id']}").status_code == 404


def test_unknown_route_uses_consistent_error_shape(client: TestClient) -> None:
    response = client.get(f"{BASE}/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
