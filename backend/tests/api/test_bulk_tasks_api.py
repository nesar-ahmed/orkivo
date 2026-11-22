"""API tests for bulk task changes and deletes: the contract a client meets.

``/workspaces/{id}/tasks/bulk-update`` and ``.../bulk-delete`` act on up to a
page of one workspace's tasks, all or nothing. A refusal names every task that
caused it in ``details``, pointing into the request body (``tasks.<index>.…``)
the way a validation error does, so a client can say which ones and why
(architecture doc sections 7 and 9).
"""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.synth import BASE, email_for, slug_for

pytestmark = pytest.mark.api

#: A well-formed id that names nothing; fixed, so every test run collects the same ids.
NOWHERE = "00000000-0000-4000-8000-000000000000"

SignIn = Callable[..., dict[str, Any]]
CreateTeam = Callable[..., dict[str, Any]]


@pytest.fixture()
def company(
    client: TestClient, second_client: TestClient, sign_in: SignIn, create_team: CreateTeam
) -> dict[str, Any]:
    """A company owned by ``client`` that ``second_client`` joined as a member."""
    owner = sign_in(client, email=email_for("api-bulk-owner"), display_name="Olive Owner")
    member = sign_in(second_client, email=email_for("api-bulk-member"), display_name="Mo Member")
    team = create_team(client, slug=slug_for("api-bulk"))
    invite = client.post(
        f"{BASE}/workspaces/{team['id']}/invites", json={"user_id": member["id"]}
    ).json()
    assert second_client.post(f"{BASE}/workspaces/invitations/{invite['id']}/accept").is_success
    return {"team": team, "owner": owner, "member": member}


def url(company: dict[str, Any], path: str = "") -> str:
    return f"{BASE}/workspaces/{company['team']['id']}/tasks{path}"


def make(client: TestClient, company: dict[str, Any], title: str, **body: Any) -> dict[str, Any]:
    response = client.post(url(company), json={"title": title, **body})
    assert response.status_code == 201, response.text
    return response.json()


def ref(task: dict[str, Any]) -> dict[str, Any]:
    return {"id": task["id"], "version": task["version"]}


def test_bulk_update_answers_with_every_task_as_it_is_now(
    client: TestClient, company: dict[str, Any]
) -> None:
    first, second = make(client, company, "First"), make(client, company, "Second")

    response = client.post(
        url(company, "/bulk-update"),
        json={
            "tasks": [ref(second), ref(first)],
            "changes": {"status": "done", "assignee_id": company["member"]["id"]},
        },
    )

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert [item["title"] for item in items] == ["Second", "First"]
    for item in items:
        assert (item["status"], item["version"]) == ("done", 2)
        assert item["assignee"] == {"id": company["member"]["id"], "display_name": "Mo Member"}
        assert item["capabilities"] == ["edit", "delete"]


def test_a_member_is_told_which_tasks_are_not_theirs(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    mine = make(second_client, company, "Mine")
    theirs = make(client, company, "Theirs")

    response = second_client.post(
        url(company, "/bulk-update"),
        json={"tasks": [ref(mine), ref(theirs)], "changes": {"priority": "high"}},
    )

    assert response.status_code == 403
    error = response.json()["error"]
    assert error["code"] == "TASK_FORBIDDEN"
    assert error["details"] == [{"field": "tasks.1.id", "message": "Not yours to change."}]
    # All or nothing: the member's own task did not change either.
    assert client.get(f"{BASE}/tasks/{mine['id']}").json()["priority"] == "medium"


def test_stale_tasks_are_named_in_a_conflict(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    first, second = make(client, company, "First"), make(client, company, "Second")
    client.patch(f"{BASE}/tasks/{first['id']}", json={"title": "Changed meanwhile"})

    response = client.post(url(company, "/bulk-delete"), json={"tasks": [ref(first), ref(second)]})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TASK_CONFLICT"
    assert response.json()["error"]["details"] == [
        {"field": "tasks.0.version", "message": "Changed by someone else."}
    ]
    assert client.get(f"{BASE}/tasks/{second['id']}").status_code == 200


def test_bulk_delete_is_a_204_and_the_tasks_are_gone(
    client: TestClient, company: dict[str, Any]
) -> None:
    first, second = make(client, company, "First"), make(client, company, "Second")

    response = client.post(
        url(company, "/bulk-delete"), json={"tasks": [ref(first), {"id": second["id"]}]}
    )

    assert response.status_code == 204
    for task in (first, second):
        assert client.get(f"{BASE}/tasks/{task['id']}").status_code == 404


def test_tasks_and_workspaces_outside_the_caller_read_as_missing(
    client: TestClient, company: dict[str, Any]
) -> None:
    task = make(client, company, "Here")
    private = client.post(f"{BASE}/tasks", json={"title": "Private"}).json()

    foreign_task = client.post(
        url(company, "/bulk-update"),
        json={"tasks": [ref(task), ref(private)], "changes": {"priority": "low"}},
    )
    unknown_workspace = client.post(
        f"{BASE}/workspaces/{uuid.uuid4()}/tasks/bulk-delete", json={"tasks": [ref(task)]}
    )

    assert foreign_task.status_code == 404
    assert foreign_task.json()["error"]["code"] == "TASK_NOT_FOUND"
    assert unknown_workspace.status_code == 404
    assert unknown_workspace.json()["error"]["code"] == "WORKSPACE_NOT_FOUND"


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"tasks": [], "changes": {"status": "done"}}, "tasks"),
        ({"tasks": [{"id": NOWHERE}], "changes": {}}, "changes"),
    ],
)
def test_malformed_requests_are_validation_errors(
    client: TestClient, company: dict[str, Any], body: dict[str, Any], field: str
) -> None:
    response = client.post(url(company, "/bulk-update"), json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert any(detail["field"].startswith(field) for detail in response.json()["error"]["details"])


@pytest.mark.parametrize("path", ["/bulk-update", "/bulk-delete"])
def test_bulk_routes_require_a_session(client: TestClient, path: str) -> None:
    response = client.post(f"{BASE}/workspaces/{uuid.uuid4()}/tasks{path}", json={})

    assert response.status_code == 401
