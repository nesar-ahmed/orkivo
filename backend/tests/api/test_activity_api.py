"""API tests for the activity log: the contract a client meets.

The log is read-only over HTTP --- there is nothing to post, patch or delete ---
and each event names what changed as ``{"from", "to"}``. A task's history is
reached exactly like the task; a workspace's feed also keeps deleted tasks
(architecture doc sections 7 and 9).
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from tests.synth import BASE

pytestmark = pytest.mark.api


def test_history_requires_a_session(client: TestClient) -> None:
    assert client.get(f"{BASE}/tasks/{uuid.uuid4()}/activity").status_code == 401
    assert client.get(f"{BASE}/workspaces/{uuid.uuid4()}/activity").status_code == 401


def test_a_status_move_reads_as_from_and_to(authed_client: TestClient) -> None:
    task = authed_client.post(f"{BASE}/tasks", json={"title": "Tracked"}).json()
    authed_client.patch(
        f"{BASE}/tasks/{task['id']}", json={"status": "done", "version": task["version"]}
    )

    history = authed_client.get(f"{BASE}/tasks/{task['id']}/activity").json()

    assert history["total"] == 2
    latest, first = history["items"]
    assert latest["verb"] == "task.updated"
    assert latest["changes"] == {"status": {"from": "todo", "to": "done"}}
    assert latest["task_version"] == 2
    assert set(latest["actor"]) == {"id", "display_name"}
    assert first["verb"] == "task.created"


def test_a_refused_save_leaves_no_trace(authed_client: TestClient) -> None:
    task = authed_client.post(f"{BASE}/tasks", json={"title": "Race"}).json()
    authed_client.patch(f"{BASE}/tasks/{task['id']}", json={"title": "First"})

    stale = authed_client.patch(
        f"{BASE}/tasks/{task['id']}", json={"title": "Stale", "version": task["version"]}
    )

    assert stale.status_code == 409
    assert authed_client.get(f"{BASE}/tasks/{task['id']}/activity").json()["total"] == 2


def test_the_feed_keeps_a_deleted_task(authed_client: TestClient) -> None:
    workspaces = authed_client.get(f"{BASE}/workspaces").json()["items"]
    private = next(item for item in workspaces if item["kind"] == "personal")
    task = authed_client.post(f"{BASE}/tasks", json={"title": "Short-lived"}).json()
    authed_client.delete(f"{BASE}/tasks/{task['id']}")

    gone = authed_client.get(f"{BASE}/tasks/{task['id']}/activity")
    feed = authed_client.get(f"{BASE}/workspaces/{private['id']}/activity").json()

    assert gone.status_code == 404
    assert gone.json()["error"]["code"] == "TASK_NOT_FOUND"
    assert [(e["verb"], e["task_title"]) for e in feed["items"]] == [
        ("task.deleted", "Short-lived"),
        ("task.created", "Short-lived"),
    ]


def test_comment_events_carry_no_text(authed_client: TestClient) -> None:
    task = authed_client.post(f"{BASE}/tasks", json={"title": "Quiet"}).json()
    comment = authed_client.post(
        f"{BASE}/tasks/{task['id']}/comments", json={"body": "confidential"}
    ).json()

    latest = authed_client.get(f"{BASE}/tasks/{task['id']}/activity").json()["items"][0]

    assert (latest["verb"], latest["comment_id"], latest["changes"]) == (
        "comment.added",
        comment["id"],
        {},
    )
    assert "confidential" not in str(latest)


@pytest.mark.parametrize("method", ["post", "patch", "delete"])
def test_the_log_cannot_be_written_over_http(authed_client: TestClient, method: str) -> None:
    task = authed_client.post(f"{BASE}/tasks", json={"title": "Read-only"}).json()

    response = getattr(authed_client, method)(f"{BASE}/tasks/{task['id']}/activity")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
