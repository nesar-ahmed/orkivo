"""Every failure answers in the documented error shape (architecture doc section 7).

``{"error": {"code", "message", "details"}}`` is a contract clients code
against --- the frontend maps ``VALIDATION_ERROR`` details onto form fields and
shows ``message`` for everything else (``lib/api/client.ts``). That only holds if
nothing answers in another shape, including the failures the framework raises by
itself rather than a route or a domain exception: an unmatched path, a wrong
method, a malformed body.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.synth import BASE, PASSWORD, email_for

pytestmark = pytest.mark.api


def error_of(response: Any) -> dict[str, Any]:
    """The error body, asserting the envelope itself is intact."""
    body = response.json()
    assert set(body) == {"error"}, f"unexpected top-level shape: {body}"
    error = body["error"]
    assert set(error) == {"code", "message", "details"}
    assert isinstance(error["details"], list)
    assert error["code"] and error["message"]
    return error


def test_method_not_allowed_keeps_the_contract(client: TestClient) -> None:
    """Raised by the router, not by a handler: the most likely shape to leak."""
    response = client.get(f"{BASE}/auth/login")

    assert response.status_code == 405
    assert error_of(response)["code"] == "METHOD_NOT_ALLOWED"
    # The framework's own hint survives the rewrite.
    assert "POST" in response.headers["allow"]


def test_unmatched_route_keeps_the_contract(client: TestClient) -> None:
    response = client.get(f"{BASE}/definitely-not-a-route")

    assert response.status_code == 404
    assert error_of(response)["code"] == "NOT_FOUND"


def test_validation_failure_names_the_field(client: TestClient) -> None:
    response = client.post(
        f"{BASE}/auth/register",
        json={"email": email_for("shape"), "password": "shortone"},
    )

    assert response.status_code == 422
    error = error_of(response)
    assert error["code"] == "VALIDATION_ERROR"
    assert [detail["field"] for detail in error["details"]] == ["password"]


def test_authentication_failure_is_machine_readable(client: TestClient) -> None:
    response = client.get(f"{BASE}/users/me")

    assert response.status_code == 401
    assert error_of(response)["code"] == "UNAUTHORIZED"


def test_domain_conflict_survives_the_handler(client: TestClient) -> None:
    payload = {"email": email_for("dupe"), "password": PASSWORD}
    assert client.post(f"{BASE}/auth/register", json=payload).status_code == 201

    conflict = client.post(f"{BASE}/auth/register", json=payload)

    assert conflict.status_code == 409
    assert error_of(conflict)["code"] == "EMAIL_ALREADY_IN_USE"


def test_invalid_path_parameter_keeps_the_contract(authed_client: TestClient) -> None:
    """A non-UUID id is a validation failure, not a traceback and not a 500.

    Authenticated, because the session dependency answers before the router
    ever looks at the parameter.
    """
    response = authed_client.get(f"{BASE}/tasks/not-a-uuid")

    assert response.status_code == 422
    error = error_of(response)
    assert error["code"] == "VALIDATION_ERROR"
    assert [detail["field"] for detail in error["details"]] == ["task_id"]
