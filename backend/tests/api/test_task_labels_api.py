"""API tests for labelling tasks: fields, filter and validation.

A task shows its labels by id, name and color, alphabetically. Labelling it with
a label from another workspace is one stable ``422``, whether or not that label
exists; ``label_ids`` replaces the set, is bounded, and cannot be ``null``; and
``?label=`` accepts only a label id or ``none`` (architecture doc sections 7 and
9).
"""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.modules.tasks.schemas import MAX_LABELS_PER_TASK
from tests.synth import BASE

pytestmark = pytest.mark.api


def private_workspace(client: TestClient) -> dict[str, Any]:
    workspaces = client.get(f"{BASE}/workspaces").json()["items"]
    return next(item for item in workspaces if item["kind"] == "personal")


def make_label(client: TestClient, name: str, color: str = "blue") -> dict[str, Any]:
    """A label in the signed-in caller's private workspace."""
    private = private_workspace(client)
    response = client.post(
        f"{BASE}/workspaces/{private['id']}/labels", json={"name": name, "color": color}
    )
    assert response.status_code == 201, response.text
    return response.json()


def chip(label: dict[str, Any]) -> dict[str, Any]:
    """A label as a task shows it."""
    return {"id": label["id"], "name": label["name"], "color": label["color"]}


def test_a_new_task_carries_no_labels(authed_client: TestClient) -> None:
    response = authed_client.post(f"{BASE}/tasks", json={"title": "Plain"})

    assert response.status_code == 201
    assert response.json()["labels"] == []


def test_labels_are_shown_alphabetically_with_their_color(authed_client: TestClient) -> None:
    docs = make_label(authed_client, "docs", "green")
    api = make_label(authed_client, "API", "purple")

    response = authed_client.post(
        f"{BASE}/tasks", json={"title": "Tagged", "label_ids": [docs["id"], api["id"]]}
    )

    assert response.status_code == 201, response.text
    assert response.json()["labels"] == [chip(api), chip(docs)]


def test_patch_replaces_and_clears_the_labels(authed_client: TestClient) -> None:
    bug = make_label(authed_client, "Bug", "red")
    docs = make_label(authed_client, "Docs")
    task = authed_client.post(
        f"{BASE}/tasks", json={"title": "Mover", "label_ids": [bug["id"]]}
    ).json()

    replaced = authed_client.patch(
        f"{BASE}/tasks/{task['id']}",
        json={"label_ids": [docs["id"]], "version": task["version"]},
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["labels"] == [chip(docs)]
    assert replaced.json()["version"] == task["version"] + 1

    untouched = authed_client.patch(f"{BASE}/tasks/{task['id']}", json={"title": "Renamed"})
    assert untouched.json()["labels"] == [chip(docs)]

    cleared = authed_client.patch(f"{BASE}/tasks/{task['id']}", json={"label_ids": []})
    assert cleared.json()["labels"] == []


def test_null_is_not_a_way_to_clear_labels(authed_client: TestClient) -> None:
    task = authed_client.post(f"{BASE}/tasks", json={"title": "Strict"}).json()

    response = authed_client.patch(f"{BASE}/tasks/{task['id']}", json={"label_ids": None})

    assert response.status_code == 422
    [detail] = response.json()["error"]["details"]
    assert detail["field"] == "label_ids"
    assert detail["message"].endswith("Send an empty list to remove every label.")


def test_a_task_carries_a_bounded_number_of_labels(authed_client: TestClient) -> None:
    too_many = [str(uuid.uuid4()) for _ in range(MAX_LABELS_PER_TASK + 1)]

    response = authed_client.post(f"{BASE}/tasks", json={"title": "Busy", "label_ids": too_many})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "label_ids"


def test_a_label_from_elsewhere_is_a_stable_422(
    client: TestClient, second_client: TestClient, sign_in: Callable[..., dict[str, Any]]
) -> None:
    sign_in(client)
    sign_in(second_client)
    theirs = make_label(second_client, "Theirs")

    for candidate in (theirs["id"], str(uuid.uuid4())):
        response = client.post(
            f"{BASE}/tasks", json={"title": "Mislabelled", "label_ids": [candidate]}
        )
        assert response.status_code == 422
        assert response.json()["error"] == {
            "code": "LABEL_NOT_IN_WORKSPACE",
            "message": "Tasks can only carry labels from their own workspace.",
            "details": [],
        }


def test_label_filter(authed_client: TestClient) -> None:
    bug = make_label(authed_client, "Bug")
    docs = make_label(authed_client, "Docs")
    for title, labels in (("Crash", [bug]), ("Guide", [docs]), ("Both", [bug, docs]), ("Bare", [])):
        authed_client.post(
            f"{BASE}/tasks",
            json={"title": title, "label_ids": [label["id"] for label in labels]},
        )

    def titles(**params: str) -> list[str]:
        response = authed_client.get(f"{BASE}/tasks", params=params)
        assert response.status_code == 200, response.text
        return [task["title"] for task in response.json()["items"]]

    assert titles(label=bug["id"]) == ["Both", "Crash"]
    assert titles(label="none") == ["Bare"]
    assert titles(label=docs["id"], search="guide") == ["Guide"]


def test_the_company_board_filters_by_label_too(
    authed_client: TestClient, team: dict[str, Any]
) -> None:
    urgent = authed_client.post(
        f"{BASE}/workspaces/{team['id']}/labels", json={"name": "Urgent", "color": "red"}
    ).json()
    tasks_url = f"{BASE}/workspaces/{team['id']}/tasks"
    authed_client.post(tasks_url, json={"title": "Now", "label_ids": [urgent["id"]]})
    authed_client.post(tasks_url, json={"title": "Later"})

    response = authed_client.get(tasks_url, params={"label": urgent["id"]})

    assert [task["title"] for task in response.json()["items"]] == ["Now"]


@pytest.mark.parametrize("value", ["urgent", "all", ""])
def test_unknown_label_filter_values_are_validation_errors(
    authed_client: TestClient, value: str
) -> None:
    response = authed_client.get(f"{BASE}/tasks", params={"label": value})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
