"""API tests for inviting only registered people, through the invite picker.

Two promises meet a client here. An invitation names an existing, enabled account
--- by id from the picker, or by exact address --- and is refused with one stable
``422`` otherwise. And the picker lists people without ever becoming a directory of
the platform: colleagues by name or part of an address, anyone else by their exact
address, never the caller (architecture doc sections 7 and 9).
"""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.auth.cookies import CSRF_HEADER_NAME, CSRF_HEADER_VALUE
from tests.synth import BASE, PASSWORD, email_for, slug_for

pytestmark = pytest.mark.api

SignIn = Callable[..., dict[str, Any]]
CreateTeam = Callable[..., dict[str, Any]]


def register(client: TestClient, label: str, name: str | None = None) -> dict[str, Any]:
    """An account that exists but is not signed in anywhere."""
    body: dict[str, Any] = {"email": email_for(label), "password": PASSWORD}
    if name:
        body["display_name"] = name
    response = client.post(f"{BASE}/auth/register", json=body)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture()
def setup(client: TestClient, sign_in: SignIn, create_team: CreateTeam) -> dict[str, Any]:
    owner = sign_in(client, email=email_for("picker-owner"), display_name="Olive Owner")
    team = create_team(client, slug=slug_for("picker"))
    return {"owner": owner, "team": team, "url": f"{BASE}/workspaces/{team['id']}"}


def candidates(client: TestClient, setup: dict[str, Any], **params: str) -> list[dict[str, Any]]:
    response = client.get(f"{setup['url']}/invite-candidates", params=params)
    assert response.status_code == 200, response.text
    return response.json()["items"]


# --- registered people only ---------------------------------------------------
def test_inviting_an_unregistered_address_is_a_stable_422(
    client: TestClient, setup: dict[str, Any]
) -> None:
    response = client.post(
        f"{setup['url']}/invites", json={"email": email_for("nobody-home")}
    )

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "INVITEE_NOT_REGISTERED",
        "message": (
            "This person does not have an Orkivo account yet. "
            "Ask them to sign up, then invite them."
        ),
        "details": [],
    }
    assert client.get(f"{setup['url']}/invites").json()["total"] == 0


def test_an_invitation_by_id_reaches_the_persons_inbox(
    client: TestClient, second_client: TestClient, setup: dict[str, Any], sign_in: SignIn
) -> None:
    joiner = sign_in(second_client, email=email_for("picked"), display_name="Pat Picked")

    created = client.post(
        f"{setup['url']}/invites", json={"user_id": joiner["id"], "role": "admin"}
    )

    assert created.status_code == 201, created.text
    assert (created.json()["email"], created.json()["role"]) == (joiner["email"], "admin")
    inbox = second_client.get(f"{BASE}/workspaces/invitations").json()["items"]
    assert [row["workspace_id"] for row in inbox] == [setup["team"]["id"]]


def test_an_unknown_id_is_the_same_422(client: TestClient, setup: dict[str, Any]) -> None:
    response = client.post(f"{setup['url']}/invites", json={"user_id": str(uuid.uuid4())})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVITEE_NOT_REGISTERED"


@pytest.mark.parametrize(
    "body", [{}, {"user_id": str(uuid.uuid4()), "email": "both@example.com"}]
)
def test_an_invitation_names_exactly_one_person(
    client: TestClient, setup: dict[str, Any], body: dict[str, Any]
) -> None:
    response = client.post(f"{setup['url']}/invites", json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# --- the picker ------------------------------------------------------------
def test_the_picker_never_lists_the_caller(
    client: TestClient, setup: dict[str, Any]
) -> None:
    by_own_address = candidates(client, setup, search=setup["owner"]["email"])

    assert by_own_address == []
    assert setup["owner"]["id"] not in {row["id"] for row in candidates(client, setup)}


def test_colleagues_are_listed_and_marked(
    client: TestClient,
    second_client: TestClient,
    setup: dict[str, Any],
    sign_in: SignIn,
    create_team: CreateTeam,
) -> None:
    """A colleague from another company shows up with no search at all."""
    colleague = sign_in(second_client, email=email_for("colleague"), display_name="Cal League")
    other = create_team(client, slug=slug_for("picker-other"))
    invite = client.post(
        f"{BASE}/workspaces/{other['id']}/invites", json={"user_id": colleague["id"]}
    ).json()
    second_client.post(f"{BASE}/workspaces/invitations/{invite['id']}/accept")

    rows = candidates(client, setup)
    by_name = candidates(client, setup, search="cal lea")

    assert rows == [
        {
            "id": colleague["id"],
            "display_name": "Cal League",
            "email": colleague["email"],
            "standing": None,
        }
    ]
    assert [row["id"] for row in by_name] == [colleague["id"]]

    client.post(f"{setup['url']}/invites", json={"user_id": colleague["id"]})
    assert candidates(client, setup)[0]["standing"] == "invited"


def test_strangers_need_their_exact_address(
    client: TestClient, setup: dict[str, Any]
) -> None:
    stranger = register(client, "far-away", name="Fay Faraway")

    assert candidates(client, setup, search="Fay") == []
    assert candidates(client, setup, search="far-away@") == []
    exact = candidates(client, setup, search=stranger["email"].upper())
    assert [(row["id"], row["standing"]) for row in exact] == [(stranger["id"], None)]


def test_the_picker_is_for_inviters_only(
    client: TestClient,
    second_client: TestClient,
    setup: dict[str, Any],
    sign_in: SignIn,
    app: FastAPI,
) -> None:
    member = sign_in(second_client, email=email_for("plain-member"))
    invite = client.post(f"{setup['url']}/invites", json={"user_id": member["id"]}).json()
    second_client.post(f"{BASE}/workspaces/invitations/{invite['id']}/accept")

    as_member = second_client.get(f"{setup['url']}/invite-candidates")
    with TestClient(app, headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE}) as elsewhere:
        sign_in(elsewhere, email=email_for("picker-outsider"))
        as_outsider = elsewhere.get(f"{setup['url']}/invite-candidates")

    assert as_member.status_code == 403
    assert as_member.json()["error"]["code"] == "WORKSPACE_FORBIDDEN"
    assert as_outsider.status_code == 404
    assert as_outsider.json()["error"]["code"] == "WORKSPACE_NOT_FOUND"
