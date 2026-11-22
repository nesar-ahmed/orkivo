"""API tests for scheduling reads: ``/me/tasks`` and the due-date parameters.

``/me/tasks`` is the caller's own work across every workspace they are in, in the
ordinary task-list envelope, soonest due first. The board routes and it share
``?status=open``, ``?due_from=`` / ``?due_to=`` (inclusive), ``?has_due_date=``
and the ``due`` and ``priority`` orders; a window that ends before it starts is
a field-level ``422`` like any other malformed parameter (architecture doc
sections 7 and 9).
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


def titles(response: Any) -> list[str]:
    assert response.status_code == 200, response.text
    return [task["title"] for task in response.json()["items"]]


@pytest.fixture()
def company(
    client: TestClient, second_client: TestClient, sign_in: SignIn, create_team: CreateTeam
) -> dict[str, Any]:
    """A company owned by ``client`` that ``second_client`` joined as a member."""
    owner = sign_in(client, email=email_for("api-mine-owner"), display_name="Olive Owner")
    member = sign_in(second_client, email=email_for("api-mine-member"), display_name="Mo Member")
    team = create_team(client, slug=slug_for("api-mine"))
    invite = client.post(f"{BASE}/workspaces/{team['id']}/invites", json={"email": member["email"]})
    second_client.post(f"{BASE}/workspaces/invitations/{invite.json()['id']}/accept")
    return {"team": team, "owner": owner, "member": member}


def test_my_tasks_requires_a_session(client: TestClient) -> None:
    response = client.get(f"{BASE}/me/tasks")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_my_tasks_spans_workspaces_soonest_first(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    team_tasks = f"{BASE}/workspaces/{company['team']['id']}/tasks"
    mine = company["member"]["id"]
    client.post(
        team_tasks, json={"title": "Team, due", "assignee_id": mine, "due_date": "2026-11-10"}
    )
    client.post(team_tasks, json={"title": "Team, not mine", "due_date": "2026-11-01"})
    second_client.post(f"{BASE}/tasks", json={"title": "Private, later", "due_date": "2026-11-20"})
    second_client.post(f"{BASE}/tasks", json={"title": "Private, undated"})

    response = second_client.get(f"{BASE}/me/tasks")

    assert titles(response) == ["Team, due", "Private, later", "Private, undated"]
    body = response.json()
    assert (body["total"], body["page"], body["pages"]) == (3, 1, 1)
    # Each task says where it lives, so a client can link to it there.
    assert body["items"][0]["workspace_id"] == company["team"]["id"]


def test_my_tasks_filters_by_workspace(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    team_id = company["team"]["id"]
    client.post(
        f"{BASE}/workspaces/{team_id}/tasks",
        json={"title": "Team", "assignee_id": company["member"]["id"]},
    )
    second_client.post(f"{BASE}/tasks", json={"title": "Private"})

    assert titles(second_client.get(f"{BASE}/me/tasks", params={"workspace": team_id})) == ["Team"]
    # A workspace the caller is not in matches nothing; it is not an error.
    assert (
        titles(second_client.get(f"{BASE}/me/tasks", params={"workspace": str(uuid.uuid4())})) == []
    )


def test_status_open_and_the_due_window(authed_client: TestClient) -> None:
    for title, due, status in (
        ("Early", "2026-11-01", "todo"),
        ("Middle", "2026-11-15", "in_progress"),
        ("Finished", "2026-11-16", "done"),
        ("Late", "2026-12-01", "todo"),
        ("Whenever", None, "todo"),
    ):
        authed_client.post(
            f"{BASE}/tasks", json={"title": title, "due_date": due, "status": status}
        )

    november = {"due_from": "2026-11-01", "due_to": "2026-11-30", "order": "due"}
    assert titles(authed_client.get(f"{BASE}/tasks", params=november)) == [
        "Early",
        "Middle",
        "Finished",
    ]
    assert titles(authed_client.get(f"{BASE}/tasks", params={**november, "status": "open"})) == [
        "Early",
        "Middle",
    ]
    assert titles(authed_client.get(f"{BASE}/me/tasks", params={"has_due_date": "false"})) == [
        "Whenever"
    ]


def test_priority_order(authed_client: TestClient) -> None:
    for title, priority in (("Low", "low"), ("High", "high"), ("Medium", "medium")):
        authed_client.post(f"{BASE}/tasks", json={"title": title, "priority": priority})

    response = authed_client.get(f"{BASE}/me/tasks", params={"order": "priority"})

    assert titles(response) == ["High", "Medium", "Low"]


@pytest.mark.parametrize("path", ["/tasks", "/me/tasks"])
def test_a_window_that_ends_before_it_starts_is_a_field_error(
    authed_client: TestClient, path: str
) -> None:
    response = authed_client.get(
        f"{BASE}{path}", params={"due_from": "2026-11-30", "due_to": "2026-11-01"}
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"] == [
        {"field": "due_to", "message": "due_to must be on or after due_from."}
    ]


@pytest.mark.parametrize(
    "params",
    [
        {"status": "finished"},
        {"due_from": "next week"},
        {"due_to": "2026-13-01"},
        {"has_due_date": "maybe"},
        {"order": "soonest"},
        {"workspace": "mine"},
    ],
)
def test_malformed_parameters_are_validation_errors(
    authed_client: TestClient, params: dict[str, str]
) -> None:
    response = authed_client.get(f"{BASE}/me/tasks", params=params)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
