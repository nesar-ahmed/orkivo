"""API tests for the users module: own-profile access and the platform console.

Authorization is asserted from the backend outward --- the UI hiding a control
is never the control itself (architecture doc sections 8.2 and 9).

These tests cover the *platform* axis only. What an account may do inside a
company is the workspaces module's business, and the split is itself something
these tests guard: no route here can make someone a member of a tenant.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.users.enums import PlatformRole
from app.modules.users.models import User
from tests.synth import BASE, PASSWORD, email_for

pytestmark = pytest.mark.api


# --- own profile ------------------------------------------------------------
def test_read_own_profile_requires_a_session(client: TestClient) -> None:
    response = client.get(f"{BASE}/users/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_read_own_profile_returns_the_authenticated_account(client: TestClient, sign_in) -> None:
    user = sign_in(client, email=email_for("profile-owner"), display_name="Profile Owner")

    response = client.get(f"{BASE}/users/me")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user["id"]
    assert body["display_name"] == "Profile Owner"
    assert body["platform_role"] == "user"


def test_profile_response_never_carries_credentials(client: TestClient, sign_in) -> None:
    sign_in(client, email=email_for("quiet"))

    body = client.get(f"{BASE}/users/me").json()

    assert "password_hash" not in body
    assert "password" not in body


def test_update_own_display_name(client: TestClient, sign_in) -> None:
    user = sign_in(client, email=email_for("rename"))
    assert user["display_name"] == "Rename"

    response = client.patch(f"{BASE}/users/me", json={"display_name": "Renamed"})

    assert response.status_code == 200
    assert response.json()["display_name"] == "Renamed"


def test_profile_patch_with_no_fields_changes_nothing(client: TestClient, sign_in) -> None:
    user = sign_in(client, email=email_for("noop"))

    response = client.patch(f"{BASE}/users/me", json={})

    assert response.status_code == 200
    assert response.json()["display_name"] == user["display_name"]


def test_profile_patch_rejects_blank_display_name(client: TestClient, sign_in) -> None:
    sign_in(client, email=email_for("blank"))

    response = client.patch(f"{BASE}/users/me", json={"display_name": " "})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_there_is_no_route_to_patch_someone_elses_profile(
    client: TestClient, second_client: TestClient, sign_in
) -> None:
    """``/users/me`` is the only self-service surface; ids are not accepted."""
    sign_in(client, email=email_for("caller"))
    other = sign_in(second_client, email=email_for("stranger"))

    response = client.patch(f"{BASE}/users/{other['id']}", json={"display_name": "Hijacked"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_no_route_here_makes_the_caller_a_tenant_member(
    client: TestClient, second_client: TestClient, sign_in
) -> None:
    """The platform API cannot grant tenancy, so it cannot be used to peek.

    A ``/users/{id}/role`` style route is exactly what a future contributor would
    add by accident; the platform route is spelled ``platform-role`` for that
    reason, and this test keeps the two axes apart.
    """
    sign_in(client, email=email_for("caller"))
    other = sign_in(second_client, email=email_for("tenant-owner"))

    guessed = client.patch(f"{BASE}/users/{other['id']}/role", json={"role": "admin"})
    platform = client.patch(
        f"{BASE}/users/{other['id']}/platform-role", json={"platform_role": "user"}
    )

    assert guessed.status_code == 404
    # Not a member of the platform console either.
    assert platform.status_code == 403


# --- platform console: directory ------------------------------------------
def test_ordinary_account_cannot_read_the_directory(client: TestClient, sign_in) -> None:
    sign_in(client, email=email_for("nobody-admin"))

    response = client.get(f"{BASE}/users")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_ordinary_account_cannot_change_platform_roles(
    client: TestClient, second_client: TestClient, sign_in
) -> None:
    sign_in(client, email=email_for("would-be-operator"))
    target = sign_in(second_client, email=email_for("target"))

    response = client.patch(
        f"{BASE}/users/{target['id']}/platform-role", json={"platform_role": "operator"}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_operator_reads_directory_with_pagination(
    operator_client: TestClient, second_client: TestClient, sign_in
) -> None:
    sign_in(second_client, email=email_for("extra-one"))
    # Registered without logging in, so the operator's own session is never replaced.
    assert (
        operator_client.post(
            f"{BASE}/auth/register",
            json={"email": email_for("extra-two"), "password": PASSWORD},
        ).status_code
        == 201
    )

    response = operator_client.get(f"{BASE}/users?page=1&page_size=2")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3  # the operator plus the two accounts
    assert body["page_size"] == 2
    assert body["pages"] == 2
    assert len(body["items"]) == 2
    assert all("password_hash" not in item for item in body["items"])


def test_operator_searches_directory_by_email(
    operator_client: TestClient, second_client: TestClient, sign_in
) -> None:
    sign_in(second_client, email=email_for("findable"))

    hit = operator_client.get(f"{BASE}/users", params={"search": "findable"})
    miss = operator_client.get(f"{BASE}/users", params={"search": "absent"})

    assert hit.status_code == 200
    assert hit.json()["total"] == 1
    assert hit.json()["items"][0]["email"] == email_for("findable")
    assert miss.json()["total"] == 0


def test_operator_promotes_an_account(
    operator_client: TestClient, second_client: TestClient, sign_in
) -> None:
    target = sign_in(second_client, email=email_for("promote-me"))

    response = operator_client.patch(
        f"{BASE}/users/{target['id']}/platform-role", json={"platform_role": "operator"}
    )

    assert response.status_code == 200
    assert response.json()["platform_role"] == "operator"


def test_operator_rejects_an_unknown_platform_role(
    operator_client: TestClient, second_client: TestClient, sign_in
) -> None:
    target = sign_in(second_client, email=email_for("bad-role"))

    response = operator_client.patch(
        f"{BASE}/users/{target['id']}/platform-role", json={"platform_role": "superuser"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_operator_cannot_change_their_own_platform_role(operator_client: TestClient) -> None:
    """Prevents an operator locking themselves out of the only operator account."""
    me = operator_client.get(f"{BASE}/users/me").json()

    response = operator_client.patch(
        f"{BASE}/users/{me['id']}/platform-role", json={"platform_role": "user"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ROLE_CHANGE_NOT_ALLOWED"


def test_platform_role_change_on_unknown_user_is_not_found(operator_client: TestClient) -> None:
    response = operator_client.patch(
        f"{BASE}/users/{uuid.uuid4()}/platform-role", json={"platform_role": "user"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"


def test_demoted_operator_loses_access_without_relogging_in(
    operator_client: TestClient, session: Session
) -> None:
    """Roles are read from the database per request, not from the token."""
    me = operator_client.get(f"{BASE}/users/me").json()
    row = session.get(User, uuid.UUID(me["id"]))
    assert row is not None
    row.platform_role = PlatformRole.USER
    session.commit()

    assert operator_client.get(f"{BASE}/users").status_code == 403
    # The same access token still identifies the account for self-service work.
    assert operator_client.get(f"{BASE}/users/me").status_code == 200
