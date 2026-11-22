"""API tests for labels: the contract a client meets.

Labels follow the project contract --- ``/workspaces/{id}/labels`` for a
tenant's collection, ``/labels/{id}`` for one label, a not-found answer for
anything outside the caller's tenants, and ``version`` for safe concurrent
edits. Deleting is for owners and admins, and keeps the tasks (architecture doc
sections 7 and 9).
"""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.auth.cookies import CSRF_HEADER_NAME, CSRF_HEADER_VALUE
from app.modules.labels import service as label_service
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
    the role that shapes a workspace's labels without being able to delete them."""
    owner = sign_in(client, email=email_for("api-label-owner"), display_name="Olive Owner")
    manager = sign_in(
        second_client, email=email_for("api-label-manager"), display_name="Max Manager"
    )
    team = create_team(client, slug=slug_for("api-labels"))
    join(client, second_client, team, manager["email"], role="manager")
    return {"team": team, "owner": owner, "manager": manager}


def labels_url(company: dict[str, Any]) -> str:
    return f"{BASE}/workspaces/{company['team']['id']}/labels"


def tasks_url(company: dict[str, Any]) -> str:
    return f"{BASE}/workspaces/{company['team']['id']}/tasks"


def make_label(client: TestClient, company: dict[str, Any], **body: Any) -> dict[str, Any]:
    response = client.post(labels_url(company), json={"name": "Bug", **body})
    assert response.status_code == 201, response.text
    return response.json()


# --- authentication --------------------------------------------------------
@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_every_label_route_requires_a_session(client: TestClient, method: str) -> None:
    call = getattr(client, method)
    url = f"{BASE}/labels/{uuid.uuid4()}"
    response = call(url, json={"name": "x"}) if method == "patch" else call(url)

    assert response.status_code == 401
    assert client.get(f"{BASE}/workspaces/{uuid.uuid4()}/labels").status_code == 401


# --- the shape -------------------------------------------------------------
def test_create_returns_201_and_the_public_shape(
    client: TestClient, company: dict[str, Any]
) -> None:
    response = client.post(labels_url(company), json={"name": "  Bug  ", "color": "red"})

    assert response.status_code == 201
    body = response.json()
    assert uuid.UUID(body["id"])
    assert body["workspace_id"] == company["team"]["id"]
    assert (body["name"], body["color"], body["version"]) == ("Bug", "red", 1)
    assert body["created_by"] == {"id": company["owner"]["id"], "display_name": "Olive Owner"}
    # The comparison key is storage, not contract.
    assert "name_key" not in body


def test_the_color_defaults_to_gray(client: TestClient, company: dict[str, Any]) -> None:
    assert make_label(client, company)["color"] == "gray"


def test_list_is_a_paginated_envelope_with_task_counts(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    busy = make_label(client, company, name="busy")
    make_label(client, company, name="Alpha")
    for title in ("One", "Two"):
        client.post(tasks_url(company), json={"title": title, "label_ids": [busy["id"]]})

    body = second_client.get(labels_url(company), params={"page_size": 1}).json()
    assert (body["total"], body["page"], body["page_size"], body["pages"]) == (2, 1, 1, 2)
    assert [item["name"] for item in body["items"]] == ["Alpha"]
    assert body["items"][0]["task_count"] == 0

    second = second_client.get(labels_url(company), params={"page": 2, "page_size": 1}).json()
    assert (second["items"][0]["name"], second["items"][0]["task_count"]) == ("busy", 2)


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"name": ""}, "name"),
        ({"name": "   "}, "name"),
        ({"name": "x" * 51}, "name"),
        ({}, "name"),
        ({"name": "Bug", "color": "chartreuse"}, "color"),
        ({"name": "Bug", "color": "#ff0000"}, "color"),
    ],
)
def test_invalid_names_and_colors_are_field_errors(
    client: TestClient, company: dict[str, Any], body: dict[str, Any], field: str
) -> None:
    response = client.post(labels_url(company), json=body)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert [detail["field"] for detail in error["details"]] == [field]


@pytest.mark.parametrize("field", ["name", "color"])
def test_a_name_or_color_cannot_be_cleared(
    client: TestClient, company: dict[str, Any], field: str
) -> None:
    label = make_label(client, company)

    response = client.patch(f"{BASE}/labels/{label['id']}", json={field: None})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == field


def test_patch_renames_and_recolors(client: TestClient, company: dict[str, Any]) -> None:
    label = make_label(client, company, color="red")

    response = client.patch(
        f"{BASE}/labels/{label['id']}",
        json={"name": "Defect", "color": "orange", "version": label["version"]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["name"], body["color"], body["version"]) == ("Defect", "orange", 2)


# --- refusals --------------------------------------------------------------
def test_a_duplicate_name_is_a_409_regardless_of_case(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    make_label(client, company)

    response = second_client.post(labels_url(company), json={"name": "BUG"})

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "LABEL_NAME_IN_USE",
        "message": "A label with this name already exists in this workspace.",
        "details": [],
    }


def test_a_full_workspace_is_a_409_that_says_how_to_fix_it(
    client: TestClient, company: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(label_service, "MAX_LABELS_PER_WORKSPACE", 1)
    make_label(client, company)

    response = client.post(labels_url(company), json={"name": "One too many"})

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "LABEL_LIMIT_REACHED"
    assert "1 labels" in error["message"]


def test_a_stale_version_is_a_409(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    label = make_label(client, company)
    second_client.patch(f"{BASE}/labels/{label['id']}", json={"name": "Defect"})

    stale = client.patch(
        f"{BASE}/labels/{label['id']}", json={"name": "Issue", "version": label["version"]}
    )
    stale_delete = client.delete(
        f"{BASE}/labels/{label['id']}", params={"version": label["version"]}
    )

    for response in (stale, stale_delete):
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "LABEL_CONFLICT"


def test_outsiders_get_the_not_found_contract(
    client: TestClient, company: dict[str, Any], app: FastAPI, sign_in: SignIn
) -> None:
    label = make_label(client, company)
    with TestClient(app, headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE}) as elsewhere:
        sign_in(elsewhere, email=email_for("api-label-outsider"))
        responses = [
            elsewhere.get(f"{BASE}/labels/{label['id']}"),
            elsewhere.patch(f"{BASE}/labels/{label['id']}", json={"name": "Mine"}),
            elsewhere.delete(f"{BASE}/labels/{label['id']}"),
        ]
        listing = elsewhere.get(labels_url(company))

    for response in responses:
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "LABEL_NOT_FOUND"
    assert listing.status_code == 404
    assert listing.json()["error"]["code"] == "WORKSPACE_NOT_FOUND"


def test_a_manager_may_edit_but_not_delete(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    label = make_label(client, company)

    recolored = second_client.patch(f"{BASE}/labels/{label['id']}", json={"color": "green"})
    deleted = second_client.delete(f"{BASE}/labels/{label['id']}")

    assert recolored.status_code == 200
    assert deleted.status_code == 403
    assert deleted.json()["error"]["code"] == "WORKSPACE_FORBIDDEN"
    assert client.get(f"{BASE}/labels/{label['id']}").status_code == 200


def test_a_member_reads_labels_but_may_not_shape_them(
    client: TestClient, company: dict[str, Any], app: FastAPI, sign_in: SignIn
) -> None:
    label = make_label(client, company)
    with TestClient(app, headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE}) as member:
        account = sign_in(member, email=email_for("api-label-plain-member"))
        join(client, member, company["team"], account["email"])
        read = member.get(f"{BASE}/labels/{label['id']}")
        refused = [
            member.post(labels_url(company), json={"name": "Mine"}),
            member.patch(f"{BASE}/labels/{label['id']}", json={"color": "green"}),
            member.delete(f"{BASE}/labels/{label['id']}"),
        ]

    assert read.status_code == 200
    for response in refused:
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "WORKSPACE_FORBIDDEN"


# --- deleting --------------------------------------------------------------
def test_deleting_a_label_keeps_its_tasks(client: TestClient, company: dict[str, Any]) -> None:
    label = make_label(client, company, color="red")
    task = client.post(
        tasks_url(company), json={"title": "Survivor", "label_ids": [label["id"]]}
    ).json()
    assert task["labels"] == [{"id": label["id"], "name": "Bug", "color": "red"}]

    deleted = client.delete(f"{BASE}/labels/{label['id']}")
    assert deleted.status_code == 204

    assert client.get(f"{BASE}/labels/{label['id']}").status_code == 404
    after = client.get(f"{BASE}/tasks/{task['id']}").json()
    assert after["labels"] == []
    assert after["version"] == task["version"] + 1
