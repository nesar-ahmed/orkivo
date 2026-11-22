"""API tests for comments: the contract a client meets.

``/tasks/{id}/comments`` for a task's conversation, ``/comments/{id}`` for one
comment. Anything outside the caller's tenants is not found; a comment the caller
can see but not change is ``COMMENT_FORBIDDEN`` (architecture doc sections 7 and 9).
"""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.synth import BASE, email_for, slug_for

pytestmark = pytest.mark.api

SignIn = Callable[..., dict[str, Any]]
CreateTeam = Callable[..., dict[str, Any]]


@pytest.fixture()
def company(
    client: TestClient, second_client: TestClient, sign_in: SignIn, create_team: CreateTeam
) -> dict[str, Any]:
    """A company owned by ``client`` that ``second_client`` joined, with one task."""
    owner = sign_in(client, email=email_for("api-talk-owner"), display_name="Olive Owner")
    member = sign_in(second_client, email=email_for("api-talk-member"), display_name="Mo Member")
    team = create_team(client, slug=slug_for("api-talk"))
    invite = client.post(
        f"{BASE}/workspaces/{team['id']}/invites", json={"user_id": member["id"]}
    ).json()
    second_client.post(f"{BASE}/workspaces/invitations/{invite['id']}/accept")
    task = client.post(f"{BASE}/workspaces/{team['id']}/tasks", json={"title": "Talk"}).json()
    return {"team": team, "owner": owner, "member": member, "task": task}


def comments_url(company: dict[str, Any]) -> str:
    return f"{BASE}/tasks/{company['task']['id']}/comments"


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_every_comment_route_requires_a_session(client: TestClient, method: str) -> None:
    call = getattr(client, method)
    url = f"{BASE}/comments/{uuid.uuid4()}"
    response = call(url, json={"body": "x"}) if method == "patch" else call(url)

    assert response.status_code == 401
    assert client.get(f"{BASE}/tasks/{uuid.uuid4()}/comments").status_code == 401


def test_a_comment_has_the_public_shape(
    second_client: TestClient, company: dict[str, Any]
) -> None:
    response = second_client.post(comments_url(company), json={"body": "On it."})

    assert response.status_code == 201, response.text
    body = response.json()
    assert uuid.UUID(body["id"])
    assert body["task_id"] == company["task"]["id"]
    assert body["body"] == "On it."
    assert body["author"] == {"id": company["member"]["id"], "display_name": "Mo Member"}
    assert body["edited_at"] is None
    assert company["member"]["email"] not in response.text


def test_the_conversation_is_a_paginated_envelope_oldest_first(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    client.post(comments_url(company), json={"body": "Question?"})
    second_client.post(comments_url(company), json={"body": "Answer."})

    page = client.get(comments_url(company), params={"page_size": 1}).json()

    assert (page["total"], page["pages"]) == (2, 2)
    assert [c["body"] for c in page["items"]] == ["Question?"]


@pytest.mark.parametrize("body", [{"body": ""}, {"body": "   "}, {"body": "x" * 10_001}, {}])
def test_an_invalid_body_is_a_field_error(
    client: TestClient, company: dict[str, Any], body: dict[str, Any]
) -> None:
    response = client.post(comments_url(company), json=body)

    assert response.status_code == 422
    assert [d["field"] for d in response.json()["error"]["details"]] == ["body"]


def test_editing_someone_elses_comment_is_a_403_with_the_reason(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    comment = second_client.post(comments_url(company), json={"body": "Mine"}).json()

    response = client.patch(f"{BASE}/comments/{comment['id']}", json={"body": "Owner's now"})

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "COMMENT_FORBIDDEN",
        "message": "Only the author can edit this comment, or an owner or admin delete it.",
        "details": [],
    }


def test_the_author_edits_and_an_owner_moderates(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    comment = second_client.post(comments_url(company), json={"body": "Draft"}).json()

    edited = second_client.patch(f"{BASE}/comments/{comment['id']}", json={"body": "Final"})
    assert edited.status_code == 200
    assert edited.json()["body"] == "Final"
    assert edited.json()["edited_at"] is not None

    removed = client.delete(f"{BASE}/comments/{comment['id']}")
    assert removed.status_code == 204
    assert client.get(comments_url(company)).json()["total"] == 0


def test_a_members_own_delete_of_someone_elses_comment_is_refused(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    comment = client.post(comments_url(company), json={"body": "Owner says"}).json()

    response = second_client.delete(f"{BASE}/comments/{comment['id']}")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "COMMENT_FORBIDDEN"


def test_an_unknown_comment_is_the_not_found_contract(
    client: TestClient, company: dict[str, Any]
) -> None:
    response = client.patch(f"{BASE}/comments/{uuid.uuid4()}", json={"body": "?"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "COMMENT_NOT_FOUND"


def test_commenting_leaves_the_task_version_alone(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    """An open editor's save must not conflict just because someone commented."""
    task = company["task"]
    second_client.post(comments_url(company), json={"body": "Drive-by"})

    saved = client.patch(
        f"{BASE}/tasks/{task['id']}", json={"title": "Renamed", "version": task["version"]}
    )

    assert saved.status_code == 200
