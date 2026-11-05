"""API tests for authentication: registration, login, rotation, logout, CSRF.

Covers the auth baseline in architecture doc section 9: generic failure
messages, httpOnly cookie transport, rotating refresh sessions with reuse
detection, and the documented CSRF header requirement for cookie-authenticated
state changes.
"""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.modules.auth import service as auth_service_module
from app.modules.auth.cookies import CSRF_HEADER_NAME, CSRF_HEADER_VALUE
from tests.synth import BASE, PASSWORD, WRONG_PASSWORD, email_for

pytestmark = pytest.mark.api

SignIn = Callable[..., dict[str, Any]]


def raw_set_cookies(response: Any) -> list[str]:
    return response.headers.get_list("set-cookie")


# --- registration ----------------------------------------------------------
def test_register_creates_account_without_exposing_secrets(client: TestClient) -> None:
    response = client.post(
        f"{BASE}/auth/register",
        json={"email": "Ada@example.com", "password": PASSWORD, "display_name": "Ada"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ada@example.com"  # normalized on storage
    assert body["display_name"] == "Ada"
    assert body["platform_role"] == "user"  # least privilege by default
    assert "password" not in body and "password_hash" not in body


def test_register_derives_display_name_when_omitted(client: TestClient) -> None:
    response = client.post(
        f"{BASE}/auth/register",
        json={"email": "nesar.ahmed@example.com", "password": PASSWORD},
    )

    assert response.status_code == 201
    assert response.json()["display_name"] == "Nesar Ahmed"


def test_register_rejects_short_password_with_field_detail(client: TestClient) -> None:
    response = client.post(
        f"{BASE}/auth/register",
        json={"email": email_for("shorty"), "password": "shortone"},
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert any(detail["field"] == "password" for detail in error["details"])


def test_register_rejects_malformed_email(client: TestClient) -> None:
    response = client.post(
        f"{BASE}/auth/register",
        json={"email": "not-an-address", "password": PASSWORD},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_duplicate_email_conflicts(client: TestClient) -> None:
    payload = {"email": email_for("once"), "password": PASSWORD}
    assert client.post(f"{BASE}/auth/register", json=payload).status_code == 201

    response = client.post(f"{BASE}/auth/register", json=payload)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_IN_USE"


# --- login -----------------------------------------------------------------
def test_login_sets_httponly_scoped_cookies_and_returns_public_user(
    client: TestClient, sign_in: SignIn
) -> None:
    user = sign_in(client, email=email_for("cookie"))

    response = client.post(
        f"{BASE}/auth/login", json={"email": email_for("cookie"), "password": PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["user"]["id"] == user["id"]
    # The body carries no token material, only expiry and the public profile.
    assert "access_token" not in response.json()
    assert "refresh_token" not in response.json()
    assert "access_token_expires_at" in response.json()

    cookies = raw_set_cookies(response)
    assert len(cookies) == 2
    assert all("HttpOnly" in value for value in cookies)
    assert all("SameSite=lax" in value for value in cookies)
    access = next(value for value in cookies if value.startswith("orkivo_access="))
    refresh = next(value for value in cookies if value.startswith("orkivo_refresh="))
    assert "Path=/;" in access
    assert "Path=/api/v1/auth;" in refresh


def test_login_with_wrong_password_and_unknown_email_share_one_message(
    client: TestClient, sign_in: SignIn
) -> None:
    sign_in(client, email=email_for("known"))

    wrong_password = client.post(
        f"{BASE}/auth/login", json={"email": email_for("known"), "password": WRONG_PASSWORD}
    )
    unknown_email = client.post(
        f"{BASE}/auth/login",
        json={"email": email_for("ghost"), "password": PASSWORD},
    )

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_email_is_case_insensitive(client: TestClient, sign_in: SignIn) -> None:
    sign_in(client, email=email_for("mixed.case"))

    response = client.post(
        f"{BASE}/auth/login",
        json={"email": "Mixed.Case@Example.com", "password": PASSWORD},
    )

    assert response.status_code == 200


def test_protected_endpoint_rejects_request_without_credential(client: TestClient) -> None:
    response = client.get(f"{BASE}/users/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_bearer_token_also_authenticates(
    client: TestClient, second_client: TestClient, sign_in: SignIn
) -> None:
    """Non-browser clients may present the access token as a bearer credential."""
    sign_in(client, email=email_for("bearer"))
    access = client.cookies.get("orkivo_access")
    assert access is not None

    # A second client holds no cookies at all: only the bearer header speaks.
    response = second_client.get(f"{BASE}/users/me", headers={"Authorization": f"Bearer {access}"})

    assert response.status_code == 200
    assert response.json()["email"] == email_for("bearer")


def test_tampered_access_token_is_rejected(
    client: TestClient, second_client: TestClient, sign_in: SignIn
) -> None:
    sign_in(client, email=email_for("tamper"))
    access = client.cookies.get("orkivo_access")
    assert access is not None

    forged = f"{access[:-2]}xx"
    response = second_client.get(f"{BASE}/users/me", headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_access_token_from_a_revoked_session_is_rejected(
    client: TestClient, second_client: TestClient, sign_in: SignIn
) -> None:
    """Logout revokes server-side: the still-valid signature is not enough."""
    sign_in(client, email=email_for("stale"))
    access = client.cookies.get("orkivo_access")
    assert access is not None

    assert client.post(f"{BASE}/auth/logout").status_code == 204

    response = second_client.get(f"{BASE}/users/me", headers={"Authorization": f"Bearer {access}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_INVALID"


# --- refresh rotation ------------------------------------------------------
def test_refresh_rotates_the_session(client: TestClient, sign_in: SignIn) -> None:
    sign_in(client, email=email_for("rotate"))
    before = client.cookies.get("orkivo_refresh")
    assert before is not None

    response = client.post(f"{BASE}/auth/refresh")

    assert response.status_code == 200
    assert client.cookies.get("orkivo_refresh") != before
    assert len(raw_set_cookies(response)) == 2


def test_replaying_a_rotated_token_revokes_the_whole_family(
    client: TestClient, second_client: TestClient, sign_in: SignIn
) -> None:
    """Reuse detection: a replayed token kills every session in the family."""
    sign_in(client, email=email_for("reuse"))
    stolen = client.cookies.get("orkivo_refresh")
    assert stolen is not None

    assert client.post(f"{BASE}/auth/refresh").status_code == 200
    current = client.cookies.get("orkivo_refresh")
    assert current is not None and current != stolen

    replay = second_client.post(
        f"{BASE}/auth/refresh",
        headers={"Cookie": f"orkivo_refresh={stolen}"},
    )

    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "SESSION_INVALID"
    # The legitimate session is revoked too: the family is treated as compromised.
    assert client.post(f"{BASE}/auth/refresh").status_code == 401
    assert client.get(f"{BASE}/users/me").status_code == 401


def test_refresh_without_session_cookie_fails(client: TestClient) -> None:
    response = client.post(f"{BASE}/auth/refresh")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_INVALID"


# --- logout ----------------------------------------------------------------
def test_logout_revokes_session_and_clears_cookies(client: TestClient, sign_in: SignIn) -> None:
    sign_in(client, email=email_for("bye"))
    assert client.get(f"{BASE}/users/me").status_code == 200

    response = client.post(f"{BASE}/auth/logout")

    assert response.status_code == 204
    cleared = {value.split("=")[0] for value in raw_set_cookies(response)}
    assert {"orkivo_access", "orkivo_refresh"} <= cleared
    assert all("Max-Age=0" in value for value in raw_set_cookies(response))
    assert client.get(f"{BASE}/users/me").status_code == 401
    assert client.post(f"{BASE}/auth/refresh").status_code == 401


def test_logout_without_session_is_idempotent(client: TestClient) -> None:
    assert client.post(f"{BASE}/auth/logout").status_code == 204


# --- csrf ------------------------------------------------------------------
def test_cookie_authenticated_state_change_without_csrf_header_is_rejected(
    unguarded_client: TestClient, sign_in: SignIn
) -> None:
    """A cross-site post carries a real session cookie but cannot set the header."""
    sign_in(unguarded_client, email=email_for("csrf-victim"))
    # The same client with the header succeeds, so the session itself is valid.
    guarded = unguarded_client.post(
        f"{BASE}/tasks",
        json={"title": "Legitimate"},
        headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
    )
    assert guarded.status_code == 201

    response = unguarded_client.post(f"{BASE}/tasks", json={"title": "Forced"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_CHECK_FAILED"
    # Only the forced write was blocked; the session is untouched.
    assert unguarded_client.get(f"{BASE}/users/me").status_code == 200


def test_reads_with_session_cookie_do_not_require_csrf_header(
    unguarded_client: TestClient, sign_in: SignIn
) -> None:
    sign_in(unguarded_client, email=email_for("reader"))

    response = unguarded_client.get(f"{BASE}/tasks")

    assert response.status_code == 200


def test_bearer_requests_are_exempt_from_the_csrf_header(unguarded_client: TestClient) -> None:
    """No ambient authority to abuse when the credential is a bearer token."""
    registered = unguarded_client.post(
        f"{BASE}/auth/register", json={"email": email_for("cli"), "password": PASSWORD}
    )
    assert registered.status_code == 201
    logged_in = unguarded_client.post(
        f"{BASE}/auth/login", json={"email": email_for("cli"), "password": PASSWORD}
    )
    assert logged_in.status_code == 200

    token = unguarded_client.cookies.get("orkivo_access")
    assert token is not None
    unguarded_client.cookies.clear()

    created = unguarded_client.post(
        f"{BASE}/tasks",
        json={"title": "From CLI"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert created.status_code == 201


# --- first-operator bootstrap (FIRST_OPERATOR_EMAIL) -------------------------
def configure_bootstrap_email(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    """Set the operator-configured bootstrap address for the auth service."""

    class _Settings:
        first_operator_email = value

    monkeypatch.setattr(auth_service_module, "get_settings", lambda: _Settings())


def test_registration_always_creates_an_ordinary_account(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even the configured address is an ordinary account until it signs in."""
    configure_bootstrap_email(monkeypatch, email_for("root"))

    response = client.post(
        f"{BASE}/auth/register", json={"email": email_for("root"), "password": PASSWORD}
    )

    assert response.status_code == 201
    assert response.json()["platform_role"] == "user"


def test_bootstrap_operator_signs_in_with_operator_role_and_console_access(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_bootstrap_email(monkeypatch, email_for("root"))
    client.post(f"{BASE}/auth/register", json={"email": email_for("root"), "password": PASSWORD})

    logged_in = client.post(
        f"{BASE}/auth/login", json={"email": email_for("root"), "password": PASSWORD}
    )

    assert logged_in.status_code == 200
    assert logged_in.json()["user"]["platform_role"] == "operator"
    assert client.get(f"{BASE}/users/me").json()["platform_role"] == "operator"
    # The role is live for this very session, not only after a second login.
    assert client.get(f"{BASE}/users").status_code == 200


def test_bootstrap_grants_operator_to_only_the_first_matching_sign_in(
    client: TestClient, second_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A lingering setting cannot hand the role to the next account."""
    configure_bootstrap_email(monkeypatch, email_for("root"))
    for jar, address in ((client, email_for("root")), (second_client, email_for("late-root"))):
        jar.post(f"{BASE}/auth/register", json={"email": address, "password": PASSWORD})
        jar.post(f"{BASE}/auth/login", json={"email": address, "password": PASSWORD})

    assert client.get(f"{BASE}/users/me").json()["platform_role"] == "operator"
    assert second_client.get(f"{BASE}/users/me").json()["platform_role"] == "user"
    assert second_client.get(f"{BASE}/users").status_code == 403


def test_bootstrap_is_off_by_default_so_registration_cannot_self_promote(
    client: TestClient,
) -> None:
    """Nothing in the request body chooses a role, with or without the setting."""
    address = email_for("wannabe")
    client.post(
        f"{BASE}/auth/register",
        json={"email": address, "password": PASSWORD, "platform_role": "operator"},
    )
    logged_in = client.post(f"{BASE}/auth/login", json={"email": address, "password": PASSWORD})

    assert logged_in.status_code == 200
    assert logged_in.json()["user"]["platform_role"] == "user"
    assert client.get(f"{BASE}/users").status_code == 403
