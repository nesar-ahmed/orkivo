"""API tests for the inbox, watching and mentions: the contract a client meets.

An inbox row names who, what and where --- never an email --- and carries enough
of the workspace to link to the task. Another person's notification is not
found. A comment lists the members it mentions, so ``<@id>`` can be shown as a
name (architecture doc sections 7 and 9).
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
    """A company owned by ``client`` (Olive) that ``second_client`` (Mo) joined."""
    olive = sign_in(client, email=email_for("api-bell-olive"), display_name="Olive Owner")
    mo = sign_in(second_client, email=email_for("api-bell-mo"), display_name="Mo Member")
    team = create_team(client, slug=slug_for("api-bell"))
    invite = client.post(
        f"{BASE}/workspaces/{team['id']}/invites", json={"user_id": mo["id"]}
    ).json()
    second_client.post(f"{BASE}/workspaces/invitations/{invite['id']}/accept")
    return {"team": team, "olive": olive, "mo": mo}


def assign_to_mo(client: TestClient, company: dict[str, Any], title: str = "Yours") -> dict:
    response = client.post(
        f"{BASE}/workspaces/{company['team']['id']}/tasks",
        json={"title": title, "assignee_id": company["mo"]["id"]},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_the_inbox_requires_a_session(client: TestClient) -> None:
    assert client.get(f"{BASE}/notifications").status_code == 401
    assert client.get(f"{BASE}/notifications/unread-count").status_code == 401
    assert client.post(f"{BASE}/notifications/read-all").status_code == 401
    assert client.get(f"{BASE}/tasks/{uuid.uuid4()}/watchers").status_code == 401


def test_an_assignment_reaches_the_inbox_in_the_public_shape(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    task = assign_to_mo(client, company)

    inbox = second_client.get(f"{BASE}/notifications")

    assert inbox.status_code == 200
    body = inbox.json()
    assert (body["total"], body["unread"], body["pages"]) == (1, 1, 1)
    row = body["items"][0]
    assert row["kind"] == "assigned"
    assert row["actor"] == {"id": company["olive"]["id"], "display_name": "Olive Owner"}
    assert row["task"] == {"id": task["id"], "title": "Yours"}
    assert row["workspace"] == {
        "id": company["team"]["id"],
        "name": company["team"]["name"],
        "kind": "team",
        "slug": company["team"]["slug"],
    }
    assert (row["comment_id"], row["excerpt"], row["read_at"]) == (None, None, None)
    assert company["olive"]["email"] not in inbox.text
    assert second_client.get(f"{BASE}/notifications/unread-count").json() == {"count": 1}


def test_reading_marks_it_read_and_only_for_its_recipient(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    assign_to_mo(client, company)
    row = second_client.get(f"{BASE}/notifications").json()["items"][0]

    stolen = client.post(f"{BASE}/notifications/{row['id']}/read")
    assert stolen.status_code == 404
    assert stolen.json()["error"]["code"] == "NOTIFICATION_NOT_FOUND"

    assert second_client.post(f"{BASE}/notifications/{row['id']}/read").status_code == 204
    assert second_client.get(f"{BASE}/notifications/unread-count").json() == {"count": 0}
    unread = second_client.get(f"{BASE}/notifications", params={"unread": "true"}).json()
    assert unread["total"] == 0


def test_read_all(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    assign_to_mo(client, company, "One")
    assign_to_mo(client, company, "Two")

    assert second_client.post(f"{BASE}/notifications/read-all").status_code == 204
    assert second_client.get(f"{BASE}/notifications/unread-count").json() == {"count": 0}


def test_watchers_endpoints(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    task = client.post(
        f"{BASE}/workspaces/{company['team']['id']}/tasks", json={"title": "Follow"}
    ).json()
    url = f"{BASE}/tasks/{task['id']}/watchers"

    before = second_client.get(url).json()
    assert before == {
        "items": [{"id": company["olive"]["id"], "display_name": "Olive Owner"}],
        "watching": False,
    }

    followed = second_client.post(url)
    assert followed.status_code == 200
    assert followed.json()["watching"] is True
    assert len(followed.json()["items"]) == 2

    assert second_client.delete(url).status_code == 204
    assert second_client.get(url).json()["watching"] is False


def test_a_comment_lists_the_members_it_mentions(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    task = client.post(
        f"{BASE}/workspaces/{company['team']['id']}/tasks", json={"title": "Ping"}
    ).json()
    stranger = uuid.uuid4()
    body = f"<@{company['mo']['id']}> can you look? (not <@{stranger}>)"

    comment = client.post(f"{BASE}/tasks/{task['id']}/comments", json={"body": body}).json()

    assert comment["body"] == body
    assert comment["mentions"] == [{"id": company["mo"]["id"], "display_name": "Mo Member"}]
    row = second_client.get(f"{BASE}/notifications").json()["items"][0]
    assert row["kind"] == "mentioned"
    assert row["comment_id"] == comment["id"]
    assert row["excerpt"] == "@Mo Member can you look? (not @someone)"
    listed = client.get(f"{BASE}/tasks/{task['id']}/comments").json()["items"][0]
    assert listed["mentions"] == comment["mentions"]
