"""API tests for projects: the contract a client meets.

Projects follow the task contract --- ``/workspaces/{id}/projects`` for a tenant's
collection, ``/projects/{id}`` for one project, a not-found answer for anything
outside the caller's tenants, and ``version`` for safe concurrent edits. Deleting
is for owners and admins, and keeps the tasks (architecture doc sections 7 and 9).
"""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.auth.cookies import CSRF_HEADER_NAME, CSRF_HEADER_VALUE
from tests.synth import BASE, email_for, slug_for

pytestmark = pytest.mark.api

# The shapes of the ``sign_in`` and ``create_team`` fixtures in ``conftest.py``.
SignIn = Callable[..., dict[str, Any]]
CreateTeam = Callable[..., dict[str, Any]]


def join(
    owner: TestClient,
    joiner: TestClient,
    team: dict[str, Any],
    email: str,
    role: str = "member",
) -> None:
    """Invite ``email`` as the owner and accept as the joiner, like a real person."""
    invite = owner.post(
        f"{BASE}/workspaces/{team['id']}/invites", json={"email": email, "role": role}
    )
    assert invite.status_code == 201, invite.text
    accepted = joiner.post(f"{BASE}/workspaces/invitations/{invite.json()['id']}/accept")
    assert accepted.status_code == 200, accepted.text


@pytest.fixture()
def company(
    client: TestClient, second_client: TestClient, sign_in: SignIn, create_team: CreateTeam
) -> dict[str, Any]:
    """A company owned by ``client`` that ``second_client`` joined as a manager:
    the role that shapes a workspace's projects without being able to delete them."""
    owner = sign_in(client, email=email_for("api-project-owner"), display_name="Olive Owner")
    manager = sign_in(
        second_client, email=email_for("api-project-manager"), display_name="Max Manager"
    )
    team = create_team(client, slug=slug_for("api-projects"))
    join(client, second_client, team, manager["email"], role="manager")
    return {"team": team, "owner": owner, "manager": manager}


def projects_url(company: dict[str, Any]) -> str:
    return f"{BASE}/workspaces/{company['team']['id']}/projects"


def tasks_url(company: dict[str, Any]) -> str:
    return f"{BASE}/workspaces/{company['team']['id']}/tasks"


def make_project(client: TestClient, company: dict[str, Any], **body: Any) -> dict[str, Any]:
    response = client.post(projects_url(company), json={"name": "Website", **body})
    assert response.status_code == 201, response.text
    return response.json()


# --- authentication --------------------------------------------------------
@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_every_project_route_requires_a_session(client: TestClient, method: str) -> None:
    call = getattr(client, method)
    url = f"{BASE}/projects/{uuid.uuid4()}"
    response = call(url, json={"name": "x"}) if method == "patch" else call(url)

    assert response.status_code == 401
    assert client.get(f"{BASE}/workspaces/{uuid.uuid4()}/projects").status_code == 401


# --- the shape -------------------------------------------------------------
def test_create_returns_201_and_the_public_shape(
    client: TestClient, company: dict[str, Any]
) -> None:
    response = client.post(
        projects_url(company), json={"name": "  Website  ", "description": "Relaunch"}
    )

    assert response.status_code == 201
    body = response.json()
    assert uuid.UUID(body["id"])
    assert body["workspace_id"] == company["team"]["id"]
    assert (body["name"], body["description"], body["version"]) == ("Website", "Relaunch", 1)
    assert body["created_by"] == {"id": company["owner"]["id"], "display_name": "Olive Owner"}
    # The comparison key is storage, not contract.
    assert "name_key" not in body


def test_list_is_a_paginated_envelope_with_task_counts(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    busy = make_project(client, company, name="busy")
    make_project(client, company, name="Alpha")
    for status in ("todo", "done"):
        client.post(
            tasks_url(company),
            json={"title": status, "status": status, "project_id": busy["id"]},
        )

    body = second_client.get(projects_url(company), params={"page_size": 1}).json()
    assert (body["total"], body["page"], body["page_size"], body["pages"]) == (2, 1, 1, 2)
    assert [item["name"] for item in body["items"]] == ["Alpha"]
    assert body["items"][0]["task_count"] == 0

    second = second_client.get(projects_url(company), params={"page": 2, "page_size": 1}).json()
    assert second["items"][0]["name"] == "busy"
    assert (second["items"][0]["task_count"], second["items"][0]["open_task_count"]) == (2, 1)


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"name": ""}, "name"),
        ({"name": "   "}, "name"),
        ({"name": "x" * 121}, "name"),
        ({}, "name"),
    ],
)
def test_invalid_names_are_field_errors(
    client: TestClient, company: dict[str, Any], body: dict[str, Any], field: str
) -> None:
    response = client.post(projects_url(company), json=body)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert [detail["field"] for detail in error["details"]] == [field]


def test_a_name_cannot_be_cleared_but_a_description_can(
    client: TestClient, company: dict[str, Any]
) -> None:
    project = make_project(client, company, description="Something")

    refused = client.patch(f"{BASE}/projects/{project['id']}", json={"name": None})
    assert refused.status_code == 422

    cleared = client.patch(f"{BASE}/projects/{project['id']}", json={"description": None})
    assert cleared.status_code == 200
    assert cleared.json()["description"] is None
    assert cleared.json()["name"] == "Website"


# --- refusals --------------------------------------------------------------
def test_a_duplicate_name_is_a_409_regardless_of_case(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    make_project(client, company)

    response = second_client.post(projects_url(company), json={"name": "WEBSITE"})

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "PROJECT_NAME_IN_USE",
        "message": "A project with this name already exists in this workspace.",
        "details": [],
    }


def test_a_stale_version_is_a_409(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    project = make_project(client, company)
    second_client.patch(f"{BASE}/projects/{project['id']}", json={"name": "Site"})

    stale = client.patch(
        f"{BASE}/projects/{project['id']}", json={"name": "Web", "version": project["version"]}
    )
    stale_delete = client.delete(
        f"{BASE}/projects/{project['id']}", params={"version": project["version"]}
    )

    for response in (stale, stale_delete):
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "PROJECT_CONFLICT"


def test_outsiders_get_the_not_found_contract(
    client: TestClient, company: dict[str, Any], app: FastAPI, sign_in: SignIn
) -> None:
    project = make_project(client, company)
    with TestClient(app, headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE}) as elsewhere:
        sign_in(elsewhere, email=email_for("api-project-outsider"))
        responses = [
            elsewhere.get(f"{BASE}/projects/{project['id']}"),
            elsewhere.patch(f"{BASE}/projects/{project['id']}", json={"name": "Mine"}),
            elsewhere.delete(f"{BASE}/projects/{project['id']}"),
        ]
        listing = elsewhere.get(projects_url(company))

    for response in responses:
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"
    assert listing.status_code == 404
    assert listing.json()["error"]["code"] == "WORKSPACE_NOT_FOUND"


def test_a_manager_may_edit_but_not_delete(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    project = make_project(client, company)

    renamed = second_client.patch(f"{BASE}/projects/{project['id']}", json={"name": "Site"})
    deleted = second_client.delete(f"{BASE}/projects/{project['id']}")

    assert renamed.status_code == 200
    assert deleted.status_code == 403
    assert deleted.json()["error"]["code"] == "WORKSPACE_FORBIDDEN"
    assert client.get(f"{BASE}/projects/{project['id']}").status_code == 200


def test_a_member_reads_projects_but_may_not_shape_them(
    client: TestClient, company: dict[str, Any], app: FastAPI, sign_in: SignIn
) -> None:
    project = make_project(client, company)
    with TestClient(app, headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE}) as member:
        account = sign_in(member, email=email_for("api-project-plain-member"))
        join(client, member, company["team"], account["email"])
        read = member.get(f"{BASE}/projects/{project['id']}")
        refused = [
            member.post(projects_url(company), json={"name": "Mine"}),
            member.patch(f"{BASE}/projects/{project['id']}", json={"name": "Site"}),
            member.delete(f"{BASE}/projects/{project['id']}"),
        ]

    assert read.status_code == 200
    for response in refused:
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "WORKSPACE_FORBIDDEN"


# --- deleting --------------------------------------------------------------
def test_deleting_a_project_keeps_its_tasks(
    client: TestClient, company: dict[str, Any]
) -> None:
    project = make_project(client, company)
    task = client.post(
        tasks_url(company), json={"title": "Survivor", "project_id": project["id"]}
    ).json()
    assert task["project"] == {"id": project["id"], "name": "Website"}

    deleted = client.delete(f"{BASE}/projects/{project['id']}")
    assert deleted.status_code == 204

    assert client.get(f"{BASE}/projects/{project['id']}").status_code == 404
    after = client.get(f"{BASE}/tasks/{task['id']}").json()
    assert after["project"] is None
    assert after["version"] == task["version"] + 1
