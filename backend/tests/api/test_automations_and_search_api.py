"""API tests for automation rules and search: the contracts a client meets.

``/workspaces/{id}/automations`` lists the catalogue and switches one rule;
``/search`` finds workspaces, projects and tasks by name in the caller's own
workspaces. Both answer outsiders with the not-found contract, and people appear
by name, never by email (architecture doc sections 7 and 9).
"""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.synth import BASE, email_for, slug_for

pytestmark = pytest.mark.api

SignIn = Callable[..., dict[str, Any]]
CreateTeam = Callable[..., dict[str, Any]]

#: A well-formed id that names nothing; fixed, so every test run collects the same ids.
NOWHERE = "00000000-0000-4000-8000-000000000000"


@pytest.fixture()
def company(
    client: TestClient, second_client: TestClient, sign_in: SignIn, create_team: CreateTeam
) -> dict[str, Any]:
    """A company owned by ``client`` that ``second_client`` joined as a member."""
    owner = sign_in(client, email=email_for("api-auto-owner"), display_name="Olive Owner")
    member = sign_in(second_client, email=email_for("api-auto-member"), display_name="Mo Member")
    team = create_team(client, name="Acme Robotics", slug=slug_for("api-auto"))
    invite = client.post(
        f"{BASE}/workspaces/{team['id']}/invites", json={"user_id": member["id"]}
    ).json()
    assert second_client.post(f"{BASE}/workspaces/invitations/{invite['id']}/accept").is_success
    return {"team": team, "owner": owner, "member": member}


def rules_url(company: dict[str, Any], rule: str = "") -> str:
    suffix = f"/{rule}" if rule else ""
    return f"{BASE}/workspaces/{company['team']['id']}/automations{suffix}"


# --- automations --------------------------------------------------------------------
def test_the_catalogue_lists_every_rule_with_what_it_does(
    second_client: TestClient, company: dict[str, Any]
) -> None:
    response = second_client.get(rules_url(company))

    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "rule": rule,
            "trigger": "task_completed",
            "recipient": recipient,
            "enabled": False,
            "updated_by": None,
            "updated_at": None,
        }
        for rule, recipient in (
            ("notify_creator_on_done", "task_creator"),
            ("notify_watchers_on_done", "task_watchers"),
            ("notify_owners_on_done", "workspace_owners"),
        )
    ]


def test_switching_a_rule_says_who_did_it_and_sends_completed_notifications(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    switched = client.patch(rules_url(company, "notify_creator_on_done"), json={"enabled": True})
    task = client.post(
        f"{BASE}/workspaces/{company['team']['id']}/tasks",
        json={"title": "Ship it", "assignee_id": company["member"]["id"]},
    ).json()

    second_client.patch(f"{BASE}/tasks/{task['id']}", json={"status": "done"})

    assert switched.status_code == 200
    assert switched.json()["enabled"] is True
    assert switched.json()["updated_by"] == {
        "id": company["owner"]["id"],
        "display_name": "Olive Owner",
    }
    newest = client.get(f"{BASE}/notifications").json()["items"][0]
    assert (newest["kind"], newest["task"]["title"], newest["actor"]["display_name"]) == (
        "completed",
        "Ship it",
        "Mo Member",
    )


def test_a_member_cannot_switch_rules(second_client: TestClient, company: dict[str, Any]) -> None:
    response = second_client.patch(
        rules_url(company, "notify_creator_on_done"), json={"enabled": True}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "WORKSPACE_FORBIDDEN"


def test_unknown_rules_outsiders_and_private_workspaces(
    client: TestClient, company: dict[str, Any]
) -> None:
    unknown = client.patch(rules_url(company, "notify_everyone"), json={"enabled": True})
    outsider = client.get(f"{BASE}/workspaces/{NOWHERE}/automations")
    private_id = next(
        item["id"]
        for item in client.get(f"{BASE}/workspaces").json()["items"]
        if item["kind"] == "personal"
    )
    private = client.patch(
        f"{BASE}/workspaces/{private_id}/automations/notify_creator_on_done", json={"enabled": True}
    )

    assert unknown.status_code == 422
    assert outsider.status_code == 404
    assert outsider.json()["error"]["code"] == "WORKSPACE_NOT_FOUND"
    assert private.status_code == 409
    assert private.json()["error"]["code"] == "PERSONAL_WORKSPACE_READONLY"


# --- search ---------------------------------------------------------------------------
def test_search_answers_with_every_kind_and_where_it_lives(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    team_id = company["team"]["id"]
    project = client.post(f"{BASE}/workspaces/{team_id}/projects", json={"name": "Acme app"}).json()
    client.post(
        f"{BASE}/workspaces/{team_id}/tasks",
        json={"title": "Acme launch", "project_id": project["id"], "due_date": "2026-11-20"},
    )

    body = second_client.get(f"{BASE}/search", params={"q": "  acme "}).json()

    workspace = {
        "id": team_id,
        "name": "Acme Robotics",
        "kind": "team",
        "slug": company["team"]["slug"],
    }
    assert body["query"] == "acme"
    assert body["workspaces"] == [workspace]
    assert body["projects"] == [{"id": project["id"], "name": "Acme app", "workspace": workspace}]
    (task,) = body["tasks"]
    assert {key: task[key] for key in ("title", "status", "priority", "due_date", "project")} == {
        "title": "Acme launch",
        "status": "todo",
        "priority": "medium",
        "due_date": "2026-11-20",
        "project": {"id": project["id"], "name": "Acme app"},
    }
    assert task["workspace"] == workspace


@pytest.mark.parametrize(
    "params", [{}, {"q": ""}, {"q": "x", "limit": 0}, {"q": "x", "limit": 21}], ids=str
)
def test_malformed_searches_are_validation_errors(
    client: TestClient, sign_in: SignIn, params: dict[str, Any]
) -> None:
    sign_in(client)

    response = client.get(f"{BASE}/search", params=params)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("path", ["/search?q=x", f"/workspaces/{NOWHERE}/automations"])
def test_search_and_automations_require_a_session(client: TestClient, path: str) -> None:
    assert client.get(f"{BASE}{path}").status_code == 401
