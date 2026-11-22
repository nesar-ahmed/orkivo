"""API tests for filing tasks under projects: fields, filter and order.

A task shows its project by id and name. Filing it under a project from another
workspace is one stable ``422``, whether or not that project exists, and
``?project=`` / ``?order=`` accept only the documented values (architecture doc
sections 7 and 9).
"""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.synth import BASE

pytestmark = pytest.mark.api


def make_project(client: TestClient, name: str) -> dict[str, Any]:
    """A project in the signed-in caller's private workspace."""
    workspaces = client.get(f"{BASE}/workspaces").json()["items"]
    private = next(item for item in workspaces if item["kind"] == "personal")
    response = client.post(f"{BASE}/workspaces/{private['id']}/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def test_a_new_task_reports_no_project(authed_client: TestClient) -> None:
    response = authed_client.post(f"{BASE}/tasks", json={"title": "Loose"})

    assert response.status_code == 201
    assert response.json()["project"] is None


def test_patch_files_moves_and_unfiles_a_task(authed_client: TestClient) -> None:
    website = make_project(authed_client, "Website")
    app = make_project(authed_client, "App")
    task = authed_client.post(f"{BASE}/tasks", json={"title": "Mover"}).json()

    filed = authed_client.patch(
        f"{BASE}/tasks/{task['id']}",
        json={"project_id": website["id"], "version": task["version"]},
    )
    assert filed.status_code == 200, filed.text
    assert filed.json()["project"] == {"id": website["id"], "name": "Website"}

    moved = authed_client.patch(f"{BASE}/tasks/{task['id']}", json={"project_id": app["id"]})
    assert moved.json()["project"]["name"] == "App"

    unfiled = authed_client.patch(f"{BASE}/tasks/{task['id']}", json={"project_id": None})
    assert unfiled.json()["project"] is None


def test_a_project_from_elsewhere_is_a_stable_422(
    client: TestClient, second_client: TestClient, sign_in: Callable[..., dict[str, Any]]
) -> None:
    sign_in(client)
    sign_in(second_client)
    theirs = make_project(second_client, "Theirs")

    for candidate in (theirs["id"], str(uuid.uuid4())):
        response = client.post(
            f"{BASE}/tasks", json={"title": "Misfiled", "project_id": candidate}
        )
        assert response.status_code == 422
        assert response.json()["error"] == {
            "code": "PROJECT_NOT_IN_WORKSPACE",
            "message": "Tasks can only be filed under a project in their own workspace.",
            "details": [],
        }


def test_project_filter_and_order(authed_client: TestClient) -> None:
    web = make_project(authed_client, "website")
    app = make_project(authed_client, "App")
    for title, project in (("Web", web), ("Loose", None), ("App", app)):
        body: dict[str, Any] = {"title": title}
        if project:
            body["project_id"] = project["id"]
        authed_client.post(f"{BASE}/tasks", json=body)

    def titles(**params: str) -> list[str]:
        response = authed_client.get(f"{BASE}/tasks", params=params)
        assert response.status_code == 200, response.text
        return [task["title"] for task in response.json()["items"]]

    assert titles(project=web["id"]) == ["Web"]
    assert titles(project="none") == ["Loose"]
    assert titles(order="project") == ["App", "Web", "Loose"]
    assert titles(order="newest") == ["App", "Loose", "Web"]


@pytest.mark.parametrize("params", [{"project": "website"}, {"order": "oldest"}])
def test_unknown_filter_values_are_validation_errors(
    authed_client: TestClient, params: dict[str, str]
) -> None:
    response = authed_client.get(f"{BASE}/tasks", params=params)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
