"""API tests for dashboards: ``/workspaces/{id}/stats`` and ``/me/stats``.

The contract a dashboard is drawn from: counts by status and by due date on the
viewer's own day, open work per priority, and workload per member (a workspace)
or per workspace (a person). People appear by name, never by email
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

COUNT_FIELDS = {
    "total",
    "todo",
    "in_progress",
    "done",
    "open",
    "overdue",
    "due_today",
    "due_next_7_days",
}


@pytest.fixture()
def company(
    client: TestClient, second_client: TestClient, sign_in: SignIn, create_team: CreateTeam
) -> dict[str, Any]:
    owner = sign_in(client, email=email_for("api-dash-owner"), display_name="Olive Owner")
    member = sign_in(second_client, email=email_for("api-dash-member"), display_name="Mo Member")
    team = create_team(client, slug=slug_for("api-dash"))
    invite = client.post(
        f"{BASE}/workspaces/{team['id']}/invites", json={"user_id": member["id"]}
    ).json()
    assert second_client.post(f"{BASE}/workspaces/invitations/{invite['id']}/accept").is_success
    return {"team": team, "owner": owner, "member": member}


def test_a_workspace_dashboard_has_counts_priorities_and_workload(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    tasks = f"{BASE}/workspaces/{company['team']['id']}/tasks"
    client.post(tasks, json={"title": "Late", "due_date": "2026-11-09", "priority": "high"})
    client.post(
        tasks,
        json={"title": "Mo's", "due_date": "2026-11-10", "assignee_id": company["member"]["id"]},
    )

    response = second_client.get(
        f"{BASE}/workspaces/{company['team']['id']}/stats", params={"today": "2026-11-10"}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["workspace_id"], body["today"]) == (company["team"]["id"], "2026-11-10")
    assert set(body["totals"]) == COUNT_FIELDS
    assert (body["totals"]["open"], body["totals"]["overdue"], body["totals"]["due_today"]) == (
        2,
        1,
        1,
    )
    assert body["open_by_priority"] == {"high": 1, "medium": 1, "low": 0}
    assert [(row["person"], row["role"], row["counts"]["open"]) for row in body["workload"]] == [
        ({"id": company["member"]["id"], "display_name": "Mo Member"}, "member", 1),
        ({"id": company["owner"]["id"], "display_name": "Olive Owner"}, "owner", 0),
        (None, None, 1),
    ]
    assert company["member"]["email"] not in response.text


def test_a_persons_dashboard_is_their_own_work_per_workspace(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    client.post(
        f"{BASE}/workspaces/{company['team']['id']}/tasks",
        json={"title": "Mo's", "assignee_id": company["member"]["id"]},
    )
    second_client.post(f"{BASE}/tasks", json={"title": "Errand"})

    body = second_client.get(f"{BASE}/me/stats").json()

    assert body["totals"]["open"] == 2
    assert [
        (row["workspace"]["kind"], row["workspace"]["slug"], row["counts"]["open"])
        for row in body["by_workspace"]
    ] == [("personal", None, 1), ("team", company["team"]["slug"], 1)]


def test_outsiders_get_the_not_found_contract(client: TestClient, company: dict[str, Any]) -> None:
    response = client.get(f"{BASE}/workspaces/{uuid.uuid4()}/stats")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "WORKSPACE_NOT_FOUND"


@pytest.mark.parametrize("today", ["1900-01-01", "not-a-date"])
def test_an_impossible_day_is_a_validation_error(
    client: TestClient, sign_in: SignIn, today: str
) -> None:
    sign_in(client)

    response = client.get(f"{BASE}/me/stats", params={"today": today})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "today"


@pytest.mark.parametrize("path", ["/me/stats", f"/workspaces/{NOWHERE}/stats"])
def test_dashboards_require_a_session(client: TestClient, path: str) -> None:
    assert client.get(f"{BASE}{path}").status_code == 401
