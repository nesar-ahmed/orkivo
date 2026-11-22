"""API tests for task assignment: the contract a client meets.

The assignee appears by name and id --- never by email --- and the error for
naming someone outside the tenant is one stable code, whether or not that
account exists. ``?assignee=`` takes a member's id, ``me`` or ``none``, and
nothing else (architecture doc sections 7 and 9).
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


def join(owner: TestClient, joiner: TestClient, team: dict[str, Any], email: str) -> None:
    """Invite ``email`` as the owner and accept as the joiner, like a real person."""
    invite = owner.post(f"{BASE}/workspaces/{team['id']}/invites", json={"email": email})
    assert invite.status_code == 201, invite.text
    accepted = joiner.post(f"{BASE}/workspaces/invitations/{invite.json()['id']}/accept")
    assert accepted.status_code == 200, accepted.text


@pytest.fixture()
def company(
    client: TestClient, second_client: TestClient, sign_in: SignIn, create_team: CreateTeam
) -> dict[str, Any]:
    """A company owned by ``client`` that ``second_client`` has joined."""
    owner = sign_in(client, email=email_for("api-assign-owner"), display_name="Olive Owner")
    member = sign_in(
        second_client, email=email_for("api-assign-member"), display_name="Mo Member"
    )
    team = create_team(client, slug=slug_for("api-assign"))
    join(client, second_client, team, member["email"])
    return {"team": team, "owner": owner, "member": member}


def tasks_url(company: dict[str, Any]) -> str:
    return f"{BASE}/workspaces/{company['team']['id']}/tasks"


# --- the shape -------------------------------------------------------------
def test_a_new_task_reports_no_assignee(authed_client: TestClient) -> None:
    response = authed_client.post(f"{BASE}/tasks", json={"title": "Unassigned"})

    assert response.status_code == 201
    assert response.json()["assignee"] is None


def test_an_assignee_is_shown_by_name_and_never_by_email(
    client: TestClient, company: dict[str, Any]
) -> None:
    member = company["member"]

    response = client.post(
        tasks_url(company), json={"title": "For Mo", "assignee_id": member["id"]}
    )

    assert response.status_code == 201, response.text
    assert response.json()["assignee"] == {"id": member["id"], "display_name": "Mo Member"}
    assert member["email"] not in response.text


def test_patch_assigns_reassigns_and_clears(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    task = client.post(tasks_url(company), json={"title": "Hand-off"}).json()

    assigned = client.patch(
        f"{BASE}/tasks/{task['id']}",
        json={"assignee_id": company["member"]["id"], "version": task["version"]},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["assignee"]["id"] == company["member"]["id"]

    # The member hands it back; the colleague's view is the same task.
    back = second_client.patch(
        f"{BASE}/tasks/{task['id']}",
        json={"assignee_id": company["owner"]["id"], "version": assigned.json()["version"]},
    )
    assert back.status_code == 200, back.text
    assert back.json()["assignee"]["display_name"] == "Olive Owner"

    cleared = client.patch(f"{BASE}/tasks/{task['id']}", json={"assignee_id": None})
    assert cleared.status_code == 200
    assert cleared.json()["assignee"] is None


# --- refusals --------------------------------------------------------------
def test_assigning_an_outsider_is_a_stable_422(
    client: TestClient, company: dict[str, Any], app: FastAPI, sign_in: SignIn
) -> None:
    # A third browser session: an account with no place in this company.
    with TestClient(app, headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE}) as elsewhere:
        outsider = sign_in(elsewhere, email=email_for("api-assign-outsider"))

    for candidate in (outsider["id"], str(uuid.uuid4())):
        response = client.post(
            tasks_url(company), json={"title": "Nope", "assignee_id": candidate}
        )
        assert response.status_code == 422
        assert response.json()["error"] == {
            "code": "ASSIGNEE_NOT_MEMBER",
            "message": "Tasks can only be assigned to members of their workspace.",
            "details": [],
        }

    assert client.get(tasks_url(company)).json()["total"] == 0


def test_a_malformed_assignee_is_a_field_error(authed_client: TestClient) -> None:
    response = authed_client.post(f"{BASE}/tasks", json={"title": "Typo", "assignee_id": "bob"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert [detail["field"] for detail in error["details"]] == ["assignee_id"]


def test_a_stale_assignment_is_a_conflict(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    # The member's own task: the owner, who may change any task, reads it, then
    # the member saves first.
    task = second_client.post(tasks_url(company), json={"title": "Race"}).json()
    second_client.patch(f"{BASE}/tasks/{task['id']}", json={"title": "Race, renamed"})

    stale = client.patch(
        f"{BASE}/tasks/{task['id']}",
        json={"assignee_id": company["owner"]["id"], "version": task["version"]},
    )

    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "TASK_CONFLICT"


# --- the filter ------------------------------------------------------------
def test_assignee_filter_accepts_an_id_me_and_none(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    url = tasks_url(company)
    client.post(url, json={"title": "Olive's", "assignee_id": company["owner"]["id"]})
    client.post(url, json={"title": "Mo's", "assignee_id": company["member"]["id"]})
    client.post(url, json={"title": "Nobody's"})

    def titles(viewer: TestClient, assignee: str) -> list[str]:
        response = viewer.get(url, params={"assignee": assignee})
        assert response.status_code == 200, response.text
        return [task["title"] for task in response.json()["items"]]

    assert titles(client, company["member"]["id"]) == ["Mo's"]
    assert titles(client, "me") == ["Olive's"]
    assert titles(second_client, "me") == ["Mo's"]
    assert titles(client, "none") == ["Nobody's"]


def test_assignee_filter_works_on_the_private_shortcut(authed_client: TestClient) -> None:
    me = authed_client.get(f"{BASE}/users/me").json()
    authed_client.post(f"{BASE}/tasks", json={"title": "Mine", "assignee_id": me["id"]})
    authed_client.post(f"{BASE}/tasks", json={"title": "Loose"})

    mine = authed_client.get(f"{BASE}/tasks", params={"assignee": "me"}).json()
    loose = authed_client.get(f"{BASE}/tasks", params={"assignee": "none"}).json()

    assert [task["title"] for task in mine["items"]] == ["Mine"]
    assert [task["title"] for task in loose["items"]] == ["Loose"]


def test_an_unknown_assignee_filter_value_is_a_validation_error(
    authed_client: TestClient,
) -> None:
    response = authed_client.get(f"{BASE}/tasks", params={"assignee": "everyone"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# --- leaving ---------------------------------------------------------------
def test_a_member_who_leaves_no_longer_holds_the_companys_tasks(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    task = client.post(
        tasks_url(company), json={"title": "Theirs", "assignee_id": company["member"]["id"]}
    ).json()

    left = second_client.delete(
        f"{BASE}/workspaces/{company['team']['id']}/members/{company['member']['id']}"
    )
    assert left.status_code == 204

    after = client.get(f"{BASE}/tasks/{task['id']}").json()
    assert after["assignee"] is None
    assert after["version"] == task["version"] + 1
    assert after["updated_by"]["id"] == company["member"]["id"]
    assert client.get(tasks_url(company), params={"assignee": "none"}).json()["total"] == 1
