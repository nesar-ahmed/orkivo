"""API tests for tenancy: cross-workspace isolation, role gates and the console.

The suite's central claim is asserted over HTTP here, because that is how a
client meets it: a tenant you are not in does not exist, a tenant you are in does
not hand you another's data, and the platform console sees lifecycle rather than
content (architecture doc sections 6 and 9).
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from tests.synth import BASE, email_for, slug_for

pytestmark = pytest.mark.api

INVITE_BODY = {"email": email_for("joiner"), "role": "member"}


def create_team(client: TestClient, name: str = "Synthetic Co", slug: str | None = None) -> dict:
    """Open a company as the already-signed-in caller."""
    response = client.post(
        f"{BASE}/workspaces",
        json={"name": name, "slug": slug or slug_for("team")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def personal_team(client: TestClient) -> dict:
    """The caller's private tenant, as the API reports it."""
    items = client.get(f"{BASE}/workspaces").json()["items"]
    personal = [item for item in items if item["kind"] == "personal"]
    assert len(personal) == 1
    return personal[0]


# --- the basics ------------------------------------------------------------
def test_workspaces_require_a_session(client: TestClient) -> None:
    assert client.get(f"{BASE}/workspaces").status_code == 401


def test_registration_comes_with_a_private_tenant(client: TestClient, sign_in) -> None:
    sign_in(client, email=email_for("solo"))

    team = personal_team(client)

    assert team["slug"] is None
    assert team["my_role"] == "owner"
    assert team["status"] == "active"


def test_creating_a_company_makes_the_creator_owner(client: TestClient, sign_in) -> None:
    sign_in(client, email=email_for("founder"))

    team = create_team(client, name="Foundry", slug=slug_for("foundry"))

    assert team["kind"] == "team"
    assert team["slug"] == slug_for("foundry")
    # The list shape carries the caller's standing, so the UI needs no guesswork.
    assert personal_team(client)["my_role"] == "owner"
    listed = client.get(f"{BASE}/workspaces").json()["items"]
    assert [t for t in listed if t["id"] == team["id"]][0]["my_role"] == "owner"


def test_a_bad_slug_is_a_field_error(client: TestClient, sign_in) -> None:
    sign_in(client, email=email_for("typo"))

    response = client.post(f"{BASE}/workspaces", json={"name": "No Good", "slug": "Not-Valid"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert [detail["field"] for detail in error["details"]] == ["slug"]


def test_a_reserved_slug_is_refused(client: TestClient, sign_in) -> None:
    """Path-routed tenants must not be able to claim a platform address."""
    sign_in(client, email=email_for("squat"))

    response = client.post(f"{BASE}/workspaces", json={"name": "Squat", "slug": "platform"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "WORKSPACE_SLUG_IN_USE"


# --- isolation -------------------------------------------------------------
def test_anoutsider_reads_a_tenant_as_not_found(
    client: TestClient, second_client: TestClient, sign_in
) -> None:
    """The guarantee multi-tenancy exists for: another company is not readable."""
    sign_in(client, email=email_for("inside"))
    team = create_team(client, slug=slug_for("private"))
    sign_in(second_client, email=email_for("outside"))

    missing = second_client.get(f"{BASE}/workspaces/{team['id']}")
    people = second_client.get(f"{BASE}/workspaces/{team['id']}/members")

    assert missing.status_code == 404
    assert people.status_code == 404
    assert missing.json()["error"]["code"] == "WORKSPACE_NOT_FOUND"
    # And the tenant is absent from their list entirely.
    assert team["id"] not in [
        item["id"] for item in second_client.get(f"{BASE}/workspaces").json()["items"]
    ]


def test_a_missing_tenant_and_a_private_one_are_indistinguishable(
    client: TestClient, second_client: TestClient, sign_in
) -> None:
    sign_in(client, email=email_for("holder"))
    team = create_team(client, slug=slug_for("secret"))
    sign_in(second_client, email=email_for("asker"))

    real = second_client.get(f"{BASE}/workspaces/{team['id']}").json()
    ghost = second_client.get(f"{BASE}/workspaces/{uuid.uuid4()}").json()

    assert real["error"]["code"] == ghost["error"]["code"]
    assert set(real["error"]) == {"code", "message", "details"}


def test_members_may_read_their_own_tenant(client: TestClient, second_client, sign_in) -> None:
    sign_in(client, email=email_for("boss"))
    team = create_team(client, slug=slug_for("shared"))
    client.post(f"{BASE}/workspaces/{team['id']}/invites", json=INVITE_BODY)
    sign_in(second_client, email=email_for("joiner"))
    invitation = second_client.get(f"{BASE}/workspaces/invitations").json()["items"][0]
    second_client.post(f"{BASE}/workspaces/invitations/{invitation['id']}/accept")

    read = second_client.get(f"{BASE}/workspaces/{team['id']}")

    assert read.status_code == 200
    assert read.json()["my_role"] == "member"


# --- role gates ------------------------------------------------------------
def test_a_member_cannot_change_roles(
    client: TestClient, second_client: TestClient, sign_in
) -> None:
    sign_in(client, email=email_for("boss"))
    team = create_team(client, slug=slug_for("gated"))
    boss = client.get(f"{BASE}/users/me").json()
    invite = client.post(f"{BASE}/workspaces/{team['id']}/invites", json=INVITE_BODY).json()
    sign_in(second_client, email=email_for("joiner"))
    accepted = second_client.post(f"{BASE}/workspaces/invitations/{invite['id']}/accept").json()
    assert accepted["my_role"] == "member"

    response = second_client.patch(
        f"{BASE}/workspaces/{team['id']}/members/{boss['id']}/role",
        json={"role": "member"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "WORKSPACE_FORBIDDEN"


def test_the_last_owner_cannot_demote_themselves(client: TestClient, sign_in) -> None:
    sign_in(client, email=email_for("alone-in-charge"))
    team = create_team(client, slug=slug_for("sole"))
    me = client.get(f"{BASE}/users/me").json()

    response = client.patch(
        f"{BASE}/workspaces/{team['id']}/members/{me['id']}/role", json={"role": "member"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "WORKSPACE_LAST_OWNER"


def test_a_personal_tenant_takes_no_invitations(client: TestClient, sign_in) -> None:
    """No one is invited into a private space --- that is what makes it private."""
    sign_in(client, email=email_for("private"))
    team = personal_team(client)

    response = client.post(f"{BASE}/workspaces/{team['id']}/invites", json=INVITE_BODY)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PERSONAL_WORKSPACE_READONLY"


# --- the invitation round trip ---------------------------------------------
def test_invitation_round_trip_without_any_mail_transport(
    client: TestClient, second_client: TestClient, sign_in
) -> None:
    sign_in(client, email=email_for("inviter"))
    team = create_team(client, slug=slug_for("hiring"))

    invite = client.post(f"{BASE}/workspaces/{team['id']}/invites", json=INVITE_BODY)

    assert invite.status_code == 201
    assert invite.json()["status"] == "pending"

    # The address registers, and finds the offer waiting --- no token, no link.
    sign_in(second_client, email=email_for("joiner"))
    mine = second_client.get(f"{BASE}/workspaces/invitations").json()["items"]
    assert [row["workspace_name"] for row in mine] == ["Synthetic Co"]
    assert mine[0]["invited_by_name"] == "Inviter"

    joined = second_client.post(f"{BASE}/workspaces/invitations/{mine[0]['id']}/accept")

    assert joined.status_code == 200
    assert joined.json()["slug"] == slug_for("hiring")
    # Nothing is left to claim.
    assert second_client.get(f"{BASE}/workspaces/invitations").json()["items"] == []


def test_accepting_a_strangers_invitation_is_refused(
    client: TestClient, second_client: TestClient, sign_in
) -> None:
    sign_in(client, email=email_for("inviter"))
    team = create_team(client, slug=slug_for("trap"))
    invite = client.post(f"{BASE}/workspaces/{team['id']}/invites", json=INVITE_BODY).json()
    sign_in(second_client, email=email_for("somebody-else"))

    response = second_client.post(f"{BASE}/workspaces/invitations/{invite['id']}/accept")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVITE_NOT_PENDING"
    assert team["id"] not in [
        item["id"] for item in second_client.get(f"{BASE}/workspaces").json()["items"]
    ]


def test_declining_leaves_the_tenant_closed(
    client: TestClient, second_client: TestClient, sign_in
) -> None:
    sign_in(client, email=email_for("inviter"))
    team = create_team(client, slug=slug_for("polite"))
    client.post(f"{BASE}/workspaces/{team['id']}/invites", json=INVITE_BODY)
    sign_in(second_client, email=email_for("joiner"))
    invitation = second_client.get(f"{BASE}/workspaces/invitations").json()["items"][0]

    declined = second_client.post(f"{BASE}/workspaces/invitations/{invitation['id']}/decline")

    assert declined.status_code == 204
    assert second_client.get(f"{BASE}/workspaces/{team['id']}").status_code == 404
    # The inviter can see the answer.
    history = client.get(f"{BASE}/workspaces/{team['id']}/invites").json()["items"]
    assert [row["status"] for row in history] == ["declined"]


def test_revoking_an_invitation_closes_the_door(
    client: TestClient, second_client: TestClient, sign_in
) -> None:
    sign_in(client, email=email_for("inviter"))
    team = create_team(client, slug=slug_for("withdrawn"))
    invite = client.post(f"{BASE}/workspaces/{team['id']}/invites", json=INVITE_BODY).json()
    sign_in(second_client, email=email_for("joiner"))

    revoked = client.delete(f"{BASE}/workspaces/{team['id']}/invites/{invite['id']}")

    assert revoked.status_code == 204
    assert second_client.get(f"{BASE}/workspaces/invitations").json()["items"] == []
    assert (
        second_client.post(f"{BASE}/workspaces/invitations/{invite['id']}/accept").status_code
        == 409
    )


# --- platform console ------------------------------------------------------
def test_the_console_is_closed_to_ordinary_accounts(client: TestClient, sign_in) -> None:
    sign_in(client, email=email_for("civilian"))

    assert client.get(f"{BASE}/platform/workspaces").status_code == 403


def test_an_operator_reads_tenants_without_reading_their_content(
    operator_client: TestClient,
) -> None:
    """The console's whole promise, pinned as a response shape."""
    listed = operator_client.get(f"{BASE}/platform/workspaces")

    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] >= 1
    for item in body["items"]:
        assert set(item) == {
            "id",
            "kind",
            "name",
            "slug",
            "status",
            "member_count",
            "created_at",
            "updated_at",
            "operator_note",
        }
        assert "email" not in str(item)  # no member address rides along


def test_an_operator_finds_a_company_by_its_slug_and_paginator(
    operator_client: TestClient, second_client: TestClient, sign_in
) -> None:
    sign_in(second_client, email=email_for("founder"))
    team = create_team(second_client, name="Findable Co", slug=slug_for("findable"))

    hit = operator_client.get(f"{BASE}/platform/workspaces", params={"search": "Findable"})
    filtered = operator_client.get(
        f"{BASE}/platform/workspaces", params={"kind": "team", "page": 1, "page_size": 1}
    )

    assert [item["id"] for item in hit.json()["items"]] == [team["id"]]
    assert filtered.json()["pages"] == filtered.json()["total"]
    assert all(item["kind"] == "team" for item in filtered.json()["items"])


def test_suspending_a_tenant_is_reversible_and_keeps_the_people(
    operator_client: TestClient,
) -> None:
    team = create_team(operator_client, name="Slacking Co", slug=slug_for("suspended"))

    suspended = operator_client.post(
        f"{BASE}/platform/workspaces/{team['id']}/suspend", json={"note": "test: billing"}
    )
    restored = operator_client.post(
        f"{BASE}/platform/workspaces/{team['id']}/activate", json={"note": "test: paid"}
    )

    assert suspended.status_code == 200
    assert suspended.json()["status"] == "suspended"
    assert suspended.json()["operator_note"] == "test: billing"
    assert suspended.json()["member_count"] == 1
    assert restored.json()["status"] == "active"
    # The membership survived the switch: nobody was silently deleted.
    assert restored.json()["member_count"] == 1


def test_a_suspended_company_admits_no_new_members(
    operator_client: TestClient, second_client: TestClient, sign_in
) -> None:
    """Suspension has to stop the thing that actually matters: fresh access.

    ``operator_client`` wraps the very same ``client`` instance, so the tenant
    side of this test runs on ``second_client`` --- otherwise signing in as the
    founder would silently replace the operator's session.
    """
    sign_in(second_client, email=email_for("founder"))
    team = create_team(second_client, name="Frozen Co", slug=slug_for("frozen"))
    created = second_client.post(
        f"{BASE}/workspaces/{team['id']}/invites", json={"email": email_for("joiner")}
    )
    assert created.status_code == 201

    suspended = operator_client.post(
        f"{BASE}/platform/workspaces/{team['id']}/suspend", json={"note": "test"}
    )
    assert suspended.status_code == 200

    sign_in(second_client, email=email_for("joiner"))
    pending = second_client.get(f"{BASE}/workspaces/invitations").json()["items"]

    response = second_client.post(f"{BASE}/workspaces/invitations/{pending[0]['id']}/accept")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "WORKSPACE_SUSPENDED"
    # Restoring reopens the door without touching the offer itself.
    operator_client.post(f"{BASE}/platform/workspaces/{team['id']}/activate", json={})
    assert (
        second_client.post(f"{BASE}/workspaces/invitations/{pending[0]['id']}/accept").status_code
        == 200
    )
