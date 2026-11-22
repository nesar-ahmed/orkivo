"""API tests for task dependencies: the contract a client meets.

``/tasks/{id}/dependencies`` lists and adds, ``/tasks/{id}/dependencies/{blocker}``
removes; every refusal has its own stable code; a task the caller cannot reach is
``TASK_NOT_FOUND``; and every task response says how many open tasks it still
waits on (architecture doc sections 7 and 9).
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

SignIn = Callable[..., dict[str, Any]]
CreateTeam = Callable[..., dict[str, Any]]


@pytest.fixture()
def company(
    client: TestClient, second_client: TestClient, sign_in: SignIn, create_team: CreateTeam
) -> dict[str, Any]:
    """A company owned by ``client`` that ``second_client`` joined as a member."""
    owner = sign_in(client, email=email_for("api-deps-owner"), display_name="Olive Owner")
    member = sign_in(second_client, email=email_for("api-deps-member"), display_name="Mo Member")
    team = create_team(client, slug=slug_for("api-deps"))
    invite = client.post(f"{BASE}/workspaces/{team['id']}/invites", json={"email": member["email"]})
    second_client.post(f"{BASE}/workspaces/invitations/{invite.json()['id']}/accept")
    return {"team": team, "owner": owner, "member": member}


def make_task(
    client: TestClient, company: dict[str, Any], title: str, **body: Any
) -> dict[str, Any]:
    response = client.post(
        f"{BASE}/workspaces/{company['team']['id']}/tasks", json={"title": title, **body}
    )
    assert response.status_code == 201, response.text
    return response.json()


def link(client: TestClient, waiting: dict[str, Any], on: dict[str, Any]) -> Any:
    return client.post(
        f"{BASE}/tasks/{waiting['id']}/dependencies", json={"blocking_task_id": on["id"]}
    )


@pytest.mark.parametrize("method", ["get", "post", "delete"])
def test_every_dependency_route_requires_a_session(client: TestClient, method: str) -> None:
    task_id = uuid.uuid4()
    if method == "delete":
        response = client.delete(f"{BASE}/tasks/{task_id}/dependencies/{uuid.uuid4()}")
    elif method == "post":
        response = client.post(
            f"{BASE}/tasks/{task_id}/dependencies", json={"blocking_task_id": str(uuid.uuid4())}
        )
    else:
        response = client.get(f"{BASE}/tasks/{task_id}/dependencies")

    assert response.status_code == 401


def test_add_list_and_remove(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    # The member holds the task that waits, so planning it is theirs to do.
    launch = make_task(client, company, "Launch", assignee_id=company["member"]["id"])
    copy = make_task(
        client,
        company,
        "Write copy",
        due_date="2026-11-12",
        assignee_id=company["member"]["id"],
    )

    added = link(second_client, launch, copy)
    assert added.status_code == 201, added.text
    assert added.json() == {
        "blocked_by": [
            {
                "id": copy["id"],
                "title": "Write copy",
                "status": "todo",
                "priority": "medium",
                "due_date": "2026-11-12",
                "assignee": {"id": company["member"]["id"], "display_name": "Mo Member"},
                # The member holds it: they may change it, not delete it.
                "capabilities": ["edit"],
            }
        ],
        "blocking": [],
    }
    other_side = client.get(f"{BASE}/tasks/{copy['id']}/dependencies").json()
    assert [task["title"] for task in other_side["blocking"]] == ["Launch"]

    removed = client.delete(f"{BASE}/tasks/{launch['id']}/dependencies/{copy['id']}")
    assert removed.status_code == 204
    assert client.get(f"{BASE}/tasks/{launch['id']}/dependencies").json()["blocked_by"] == []


def test_task_responses_count_open_blockers(client: TestClient, company: dict[str, Any]) -> None:
    launch = make_task(client, company, "Launch")
    assert launch["open_blocker_count"] == 0
    first = make_task(client, company, "First")
    link(client, launch, first)
    link(client, launch, make_task(client, company, "Finished", status="done"))

    assert client.get(f"{BASE}/tasks/{launch['id']}").json()["open_blocker_count"] == 1
    listed = client.get(f"{BASE}/workspaces/{company['team']['id']}/tasks").json()["items"]
    assert {task["title"]: task["open_blocker_count"] for task in listed}["Launch"] == 1

    done = client.patch(f"{BASE}/tasks/{first['id']}", json={"status": "done"})
    assert done.status_code == 200
    assert client.get(f"{BASE}/tasks/{launch['id']}").json()["open_blocker_count"] == 0


@pytest.mark.parametrize(
    ("case", "status", "code"),
    [
        ("itself", 422, "DEPENDENCY_ON_ITSELF"),
        ("missing", 422, "DEPENDENCY_NOT_IN_WORKSPACE"),
        ("twice", 409, "DEPENDENCY_EXISTS"),
        ("loop", 409, "DEPENDENCY_CYCLE"),
    ],
)
def test_each_refusal_has_a_stable_code(
    client: TestClient, company: dict[str, Any], case: str, status: int, code: str
) -> None:
    a, b = make_task(client, company, "A"), make_task(client, company, "B")
    if case == "itself":
        response = link(client, a, a)
    elif case == "missing":
        response = link(client, a, {"id": str(uuid.uuid4())})
    elif case == "twice":
        link(client, a, b)
        response = link(client, a, b)
    else:
        link(client, b, a)
        response = link(client, a, b)

    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_removing_a_link_that_is_not_there_is_a_404(
    client: TestClient, company: dict[str, Any]
) -> None:
    a, b = make_task(client, company, "A"), make_task(client, company, "B")

    response = client.delete(f"{BASE}/tasks/{a['id']}/dependencies/{b['id']}")

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "DEPENDENCY_NOT_FOUND",
        "message": "This task is not blocked by that task.",
        "details": [],
    }


def test_outsiders_get_the_task_not_found_contract(
    client: TestClient, company: dict[str, Any], app: FastAPI, sign_in: SignIn
) -> None:
    a, b = make_task(client, company, "A"), make_task(client, company, "B")
    with TestClient(app, headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE}) as elsewhere:
        sign_in(elsewhere, email=email_for("api-deps-outsider"))
        responses = [
            elsewhere.get(f"{BASE}/tasks/{a['id']}/dependencies"),
            link(elsewhere, a, b),
            elsewhere.delete(f"{BASE}/tasks/{a['id']}/dependencies/{b['id']}"),
        ]

    for response in responses:
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TASK_NOT_FOUND"


def test_a_malformed_body_is_a_field_error(client: TestClient, company: dict[str, Any]) -> None:
    a = make_task(client, company, "A")

    response = client.post(
        f"{BASE}/tasks/{a['id']}/dependencies", json={"blocking_task_id": "not-a-task"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "blocking_task_id"


def test_the_assignee_hears_when_their_task_is_unblocked(
    client: TestClient, second_client: TestClient, company: dict[str, Any]
) -> None:
    launch = make_task(client, company, "Launch", assignee_id=company["member"]["id"])
    copy = make_task(client, company, "Write copy")
    link(client, launch, copy)

    client.patch(f"{BASE}/tasks/{copy['id']}", json={"status": "done"})

    inbox = second_client.get(f"{BASE}/notifications").json()["items"]
    unblocked = [item for item in inbox if item["kind"] == "unblocked"]
    assert len(unblocked) == 1
    assert unblocked[0]["task"]["title"] == "Launch"
    assert unblocked[0]["actor"]["display_name"] == "Olive Owner"
