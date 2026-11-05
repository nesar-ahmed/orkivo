"""API tests for authorization on the tasks endpoints.

Two things are asserted separately, because they fail differently in real code:
authentication (is there a valid session?) and authorization (is this *your*
resource?). Foreign resources answer with the same not-found contract as missing
ones, so the API never confirms that another user holds an id
(architecture doc sections 7 and 9).
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.modules.auth.tokens import create_access_token
from app.modules.users.enums import PlatformRole
from tests.synth import BASE, PASSWORD, email_for

pytestmark = pytest.mark.api


def test_anonymous_read_is_rejected(client: TestClient) -> None:
    response = client.get(f"{BASE}/tasks")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_anonymous_write_is_rejected(client: TestClient) -> None:
    response = client.post(f"{BASE}/tasks", json={"title": "Should not exist"})

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Sign in is required to use this endpoint."


@pytest.mark.parametrize("method", ["get", "post", "patch", "delete"])
def test_every_task_method_requires_a_session(client: TestClient, method: str) -> None:
    call = getattr(client, method)
    url = f"{BASE}/tasks" if method == "post" else f"{BASE}/tasks/{uuid.uuid4()}"
    response = call(url, json={"title": "x"}) if method in {"post", "patch"} else call(url)

    assert response.status_code == 401


def test_second_user_sees_only_their_own_tasks(
    client: TestClient, second_client: TestClient, sign_in
) -> None:
    sign_in(client, email=email_for("owner-one"))
    sign_in(second_client, email=email_for("owner-two"))

    for index in range(2):
        assert client.post(f"{BASE}/tasks", json={"title": f"Mine {index}"}).status_code == 201
    assert second_client.post(f"{BASE}/tasks", json={"title": "Theirs"}).status_code == 201

    mine = client.get(f"{BASE}/tasks").json()
    theirs = second_client.get(f"{BASE}/tasks").json()

    assert mine["total"] == 2
    assert [task["title"] for task in mine["items"]] == ["Mine 1", "Mine 0"]
    assert theirs["total"] == 1
    assert [task["title"] for task in theirs["items"]] == ["Theirs"]


def test_foreign_task_read_update_and_delete_all_answer_not_found(
    client: TestClient, second_client: TestClient, sign_in
) -> None:
    sign_in(client, email=email_for("target-owner"))
    task = client.post(f"{BASE}/tasks", json={"title": "Private"}).json()

    sign_in(second_client, email=email_for("intruder"))

    read = second_client.get(f"{BASE}/tasks/{task['id']}")
    update = second_client.patch(f"{BASE}/tasks/{task['id']}", json={"status": "done"})
    remove = second_client.delete(f"{BASE}/tasks/{task['id']}")

    for response in (read, update, remove):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TASK_NOT_FOUND"

    # The victim's task is untouched.
    assert client.get(f"{BASE}/tasks/{task['id']}").json()["status"] == "todo"


def test_foreign_and_missing_tasks_are_indistinguishable(
    client: TestClient, second_client: TestClient, sign_in
) -> None:
    sign_in(client, email=email_for("secret-holder"))
    task = client.post(f"{BASE}/tasks", json={"title": "Secret"}).json()

    sign_in(second_client, email=email_for("prober"))

    foreign = second_client.get(f"{BASE}/tasks/{task['id']}")
    missing = second_client.get(f"{BASE}/tasks/{uuid.uuid4()}")

    assert foreign.status_code == missing.status_code
    assert foreign.json() == missing.json()


def test_operator_role_grants_no_extra_task_visibility(
    client: TestClient, second_client: TestClient, sign_in
) -> None:
    """The platform role gates the console, never other people's data.

    This is the guarantee the multi-tenant step rests on: an operator runs the
    platform, and is not thereby a member of anyone's company.
    """
    sign_in(client, email=email_for("plain-user"))
    task = client.post(f"{BASE}/tasks", json={"title": "Ours"}).json()

    sign_in(second_client, email=email_for("boss"), platform_role=PlatformRole.OPERATOR)

    listing = second_client.get(f"{BASE}/tasks").json()
    assert listing["total"] == 0
    assert second_client.get(f"{BASE}/tasks/{task['id']}").status_code == 404
    # Their own tenants only: operating the platform adds none.
    mine = second_client.get(f"{BASE}/workspaces").json()
    assert [w["kind"] for w in mine["items"]] == ["personal"]


def test_search_and_filters_stay_scoped_to_the_owner(
    client: TestClient, second_client: TestClient, sign_in
) -> None:
    sign_in(client, email=email_for("searcher"))
    client.post(f"{BASE}/tasks", json={"title": "Quarterly report"})

    sign_in(second_client, email=email_for("other-searcher"))

    hit = client.get(f"{BASE}/tasks", params={"search": "Quarterly"}).json()
    miss = second_client.get(f"{BASE}/tasks", params={"search": "Quarterly"}).json()
    by_status = second_client.get(f"{BASE}/tasks", params={"status": "todo"}).json()

    assert hit["total"] == 1
    assert miss["total"] == 0
    assert by_status["total"] == 0


def test_two_sessions_for_one_account_expire_independently(
    client: TestClient, second_client: TestClient, sign_in
) -> None:
    """Signing one device out must not silently sign the other one out."""
    sign_in(client, email=email_for("shared-account"))
    # Same account on a second device: log in again, do not register again.
    second_login = second_client.post(
        f"{BASE}/auth/login",
        json={"email": email_for("shared-account"), "password": PASSWORD},
    )
    assert second_login.status_code == 200

    assert client.post(f"{BASE}/auth/logout").status_code == 204

    assert client.get(f"{BASE}/users/me").status_code == 401
    assert second_client.get(f"{BASE}/users/me").status_code == 200


def test_expired_access_token_is_rejected(
    client: TestClient, second_client: TestClient, sign_in
) -> None:
    user = sign_in(client, email=email_for("clock"))
    expired = create_access_token(uuid.UUID(user["id"]), uuid.uuid4(), ttl_seconds=-1)

    # A client with no cookies at all: the expired bearer token is the credential.
    response = second_client.get(
        f"{BASE}/users/me",
        headers={"Authorization": f"Bearer {expired.token}"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
