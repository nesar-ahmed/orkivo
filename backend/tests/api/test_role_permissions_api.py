"""API tests for workspace roles: the contract a client meets in each role.

Five roles, one company. What each may do is decided by the access policy and
re-checked on every request; what the client is *told* it may do --- a workspace's
``capabilities`` and ``grantable_roles``, a task's ``capabilities`` --- comes from
the same decision, so a screen never offers a control the next request refuses
(architecture doc sections 7 and 9).

Every person is a separate browser session with its own cookie jar, and joins the
way the product does: invited by the owner, then accepting.
"""

from collections.abc import Callable, Generator
from contextlib import ExitStack
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.auth.cookies import CSRF_HEADER_NAME, CSRF_HEADER_VALUE
from tests.synth import BASE, email_for, slug_for

pytestmark = pytest.mark.api

SignIn = Callable[..., dict[str, Any]]
CreateTeam = Callable[..., dict[str, Any]]

ROLES = ("admin", "manager", "member", "colleague", "viewer")


class Company:
    """One company: the owner's browser plus one browser per other role."""

    def __init__(self, team: dict[str, Any], people: dict[str, tuple[TestClient, Any]]) -> None:
        self.team = team
        self.clients = {role: client for role, (client, _user) in people.items()}
        self.users = {role: user for role, (_client, user) in people.items()}

    @property
    def tasks_url(self) -> str:
        return f"{BASE}/workspaces/{self.team['id']}/tasks"

    def task(self, by: str, **body: Any) -> dict[str, Any]:
        response = self.clients[by].post(self.tasks_url, json={"title": "Shared", **body})
        assert response.status_code == 201, response.text
        return response.json()


@pytest.fixture()
def company(
    app: FastAPI, client: TestClient, sign_in: SignIn, create_team: CreateTeam
) -> Generator[Company, None, None]:
    owner = sign_in(client, email=email_for("roles-owner"), display_name="Olive Owner")
    team = create_team(client, slug=slug_for("roles"))
    people: dict[str, tuple[TestClient, Any]] = {"owner": (client, owner)}
    with ExitStack() as stack:
        for role in ROLES:
            browser = stack.enter_context(
                TestClient(app, headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE})
            )
            account = sign_in(browser, email=email_for(f"roles-{role}"))
            offered = "member" if role == "colleague" else role
            invite = client.post(
                f"{BASE}/workspaces/{team['id']}/invites",
                json={"user_id": account["id"], "role": offered},
            )
            assert invite.status_code == 201, invite.text
            accepted = browser.post(f"{BASE}/workspaces/invitations/{invite.json()['id']}/accept")
            assert accepted.status_code == 200, accepted.text
            people[role] = (browser, account)
        yield Company(team, people)


# --- what a workspace tells each role --------------------------------------------
@pytest.mark.parametrize(
    ("role", "capabilities", "grantable"),
    [
        (
            "owner",
            [
                "read",
                "edit_content",
                "comment",
                "manage_tasks",
                "manage_projects",
                "manage_labels",
                "manage_automations",
                "leave",
                "view_invites",
                "manage",
                "invite",
                "change_roles",
            ],
            ["owner", "admin", "manager", "member", "viewer"],
        ),
        (
            "admin",
            [
                "read",
                "edit_content",
                "comment",
                "manage_tasks",
                "manage_projects",
                "manage_labels",
                "manage_automations",
                "leave",
                "view_invites",
                "manage",
                "invite",
                "change_roles",
            ],
            ["manager", "member", "viewer"],
        ),
        (
            "manager",
            [
                "read",
                "edit_content",
                "comment",
                "manage_tasks",
                "manage_projects",
                "manage_labels",
                "manage_automations",
                "leave",
            ],
            [],
        ),
        ("member", ["read", "edit_content", "comment", "leave"], []),
        ("viewer", ["read", "leave"], []),
    ],
)
def test_each_role_is_told_what_it_may_do(
    company: Company, role: str, capabilities: list[str], grantable: list[str]
) -> None:
    body = company.clients[role].get(f"{BASE}/workspaces/{company.team['id']}").json()

    assert body["my_role"] == role
    assert body["capabilities"] == capabilities
    assert body["grantable_roles"] == grantable


def test_the_workspace_list_carries_the_same_answer(company: Company) -> None:
    items = company.clients["viewer"].get(f"{BASE}/workspaces").json()["items"]
    team = next(item for item in items if item["id"] == company.team["id"])

    assert (team["my_role"], team["capabilities"], team["grantable_roles"]) == (
        "viewer",
        ["read", "leave"],
        [],
    )


# --- what a task tells each role ---------------------------------------------------
def test_every_task_response_lists_what_the_caller_may_do_to_it(company: Company) -> None:
    member = company.users["member"]
    created = company.task("member")
    held = company.task("owner", assignee_id=member["id"])
    others = company.task("colleague")

    def seen(role: str) -> dict[str, list[str]]:
        items = company.clients[role].get(company.tasks_url).json()["items"]
        return {item["id"]: item["capabilities"] for item in items}

    assert seen("member") == {
        created["id"]: ["edit", "delete"],
        held["id"]: ["edit"],
        others["id"]: [],
    }
    assert set(map(tuple, seen("manager").values())) == {("edit", "delete")}
    assert set(map(tuple, seen("viewer").values())) == {()}

    # One task, the caller's own list, and the answer to a save say the same thing.
    one = company.clients["member"].get(f"{BASE}/tasks/{held['id']}").json()
    mine = company.clients["member"].get(f"{BASE}/me/tasks").json()["items"]
    saved = company.clients["member"].patch(
        f"{BASE}/tasks/{held['id']}", json={"status": "in_progress"}
    )
    assert one["capabilities"] == ["edit"]
    assert {item["id"]: item["capabilities"] for item in mine}[held["id"]] == ["edit"]
    assert saved.json()["capabilities"] == ["edit"]
    assert created["capabilities"] == ["edit", "delete"]


def test_a_member_reaching_for_someone_elses_task_is_told_why(company: Company) -> None:
    task = company.task("colleague")
    member = company.clients["member"]

    changed = member.patch(f"{BASE}/tasks/{task['id']}", json={"title": "Hijacked"})
    deleted = member.delete(f"{BASE}/tasks/{task['id']}")

    for response in (changed, deleted):
        assert response.status_code == 403
        assert response.json()["error"] == {
            "code": "TASK_FORBIDDEN",
            "message": (
                "You can change only tasks you created or are assigned to, and delete only "
                "tasks you created. Ask a manager, admin or owner."
            ),
            "details": [],
        }
    assert company.clients["owner"].get(f"{BASE}/tasks/{task['id']}").json()["version"] == 1


def test_a_viewer_reads_along_and_changes_nothing(company: Company) -> None:
    viewer = company.clients["viewer"]
    task = company.task("owner", assignee_id=company.users["viewer"]["id"])
    team_id = company.team["id"]

    assert viewer.get(f"{BASE}/tasks/{task['id']}").status_code == 200
    assert viewer.get(f"{BASE}/tasks/{task['id']}/comments").status_code == 200
    # Following a task is the viewer's own setting, not the company's content.
    assert viewer.post(f"{BASE}/tasks/{task['id']}/watchers").status_code == 200
    refused = [
        viewer.post(company.tasks_url, json={"title": "Mine"}),
        viewer.patch(f"{BASE}/tasks/{task['id']}", json={"title": "Nope"}),
        viewer.delete(f"{BASE}/tasks/{task['id']}"),
        viewer.post(f"{BASE}/tasks/{task['id']}/comments", json={"body": "Hello"}),
        viewer.post(f"{BASE}/workspaces/{team_id}/projects", json={"name": "Mine"}),
        viewer.post(f"{BASE}/workspaces/{team_id}/labels", json={"name": "Mine"}),
    ]

    for response in refused:
        assert response.status_code == 403, response.request.url
        assert response.json()["error"]["code"] == "WORKSPACE_FORBIDDEN"


def test_a_member_comments_on_tasks_they_may_not_change(company: Company) -> None:
    task = company.task("colleague")

    response = company.clients["member"].post(
        f"{BASE}/tasks/{task['id']}/comments", json={"body": "Can I help?"}
    )

    assert response.status_code == 201


# --- handing out roles ----------------------------------------------------------
def test_an_admin_grants_up_to_manager_and_never_touches_an_admin(
    company: Company, app: FastAPI, sign_in: SignIn
) -> None:
    admin = company.clients["admin"]
    team_id = company.team["id"]
    member_id = company.users["member"]["id"]

    promoted = admin.patch(
        f"{BASE}/workspaces/{team_id}/members/{member_id}/role", json={"role": "manager"}
    )
    to_admin = admin.patch(
        f"{BASE}/workspaces/{team_id}/members/{member_id}/role", json={"role": "admin"}
    )
    demote_owner = admin.patch(
        f"{BASE}/workspaces/{team_id}/members/{company.users['owner']['id']}/role",
        json={"role": "viewer"},
    )

    assert promoted.status_code == 200 and promoted.json()["role"] == "manager"
    for response in (to_admin, demote_owner):
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "WORKSPACE_FORBIDDEN"

    with TestClient(app, headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE}) as newcomer:
        account = sign_in(newcomer, email=email_for("roles-newcomer"))
        as_admin = admin.post(
            f"{BASE}/workspaces/{team_id}/invites",
            json={"user_id": account["id"], "role": "admin"},
        )
        as_viewer = admin.post(
            f"{BASE}/workspaces/{team_id}/invites",
            json={"user_id": account["id"], "role": "viewer"},
        )

    assert as_admin.status_code == 403
    assert as_viewer.status_code == 201 and as_viewer.json()["role"] == "viewer"


def test_an_invitation_still_cannot_offer_ownership(company: Company) -> None:
    response = company.clients["owner"].post(
        f"{BASE}/workspaces/{company.team['id']}/invites",
        json={"email": email_for("roles-ambitious"), "role": "owner"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_a_link_is_changed_by_whoever_may_change_the_task_that_waits(company: Company) -> None:
    """Both sides of a link say what the caller may do to them, so a client can tell
    which links it may remove without knowing the rule."""
    member = company.clients["member"]
    mine = company.task("member")
    theirs = company.task("colleague")
    linked = company.clients["owner"].post(
        f"{BASE}/tasks/{theirs['id']}/dependencies", json={"blocking_task_id": mine["id"]}
    )
    assert linked.status_code == 201, linked.text

    seen = member.get(f"{BASE}/tasks/{mine['id']}/dependencies").json()
    unlink = member.delete(f"{BASE}/tasks/{theirs['id']}/dependencies/{mine['id']}")
    link = member.post(
        f"{BASE}/tasks/{mine['id']}/dependencies", json={"blocking_task_id": theirs["id"]}
    )

    assert [(task["id"], task["capabilities"]) for task in seen["blocking"]] == [(theirs["id"], [])]
    assert unlink.status_code == 403
    assert unlink.json()["error"]["code"] == "TASK_FORBIDDEN"
    # Their own task may wait on anything readable --- except a loop, which this is.
    assert link.status_code == 409
    assert link.json()["error"]["code"] == "DEPENDENCY_CYCLE"


# --- the endpoints added since: one table, every role ----------------------------------
#: Per role: (stats, see automations, switch automations, bulk-edit the owner's task).
NEWER_ENDPOINTS: dict[str, tuple[int, int, int, int]] = {
    "owner": (200, 200, 200, 200),
    "admin": (200, 200, 200, 200),
    "manager": (200, 200, 200, 200),
    "member": (200, 200, 403, 403),
    "viewer": (200, 200, 403, 403),
}


@pytest.mark.parametrize("role", list(NEWER_ENDPOINTS))
def test_newer_endpoints_follow_the_same_roles(company: Company, role: str) -> None:
    """Dashboards, automations, bulk edits and search answer each role by the same
    access table as everything else --- a cross-check over every later phase."""
    task = company.task("owner")
    browser = company.clients[role]
    team = f"{BASE}/workspaces/{company.team['id']}"

    stats = browser.get(f"{team}/stats")
    rules = browser.get(f"{team}/automations")
    switch = browser.patch(f"{team}/automations/notify_creator_on_done", json={"enabled": True})
    bulk = browser.post(
        f"{team}/tasks/bulk-update",
        json={"tasks": [{"id": task["id"]}], "changes": {"priority": "high"}},
    )
    found = browser.get(f"{BASE}/search", params={"q": "Shared"}).json()["tasks"]

    assert (stats.status_code, rules.status_code, switch.status_code, bulk.status_code) == (
        NEWER_ENDPOINTS[role]
    )
    # Everyone in the company may read its work, so everyone finds it.
    assert [hit["id"] for hit in found] == [task["id"]]
    if bulk.status_code == 403:
        # A member is told the task is not theirs; a viewer, that their role reads only.
        expected = "TASK_FORBIDDEN" if role == "member" else "WORKSPACE_FORBIDDEN"
        assert bulk.json()["error"]["code"] == expected


def test_an_outsider_meets_the_not_found_contract_everywhere_new(
    company: Company, app: FastAPI, sign_in: SignIn
) -> None:
    task = company.task("owner")
    team = f"{BASE}/workspaces/{company.team['id']}"
    with TestClient(app, headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE}) as outsider:
        sign_in(outsider, email=email_for("roles-outsider"))
        responses = [
            outsider.get(f"{team}/stats"),
            outsider.get(f"{team}/automations"),
            outsider.patch(f"{team}/automations/notify_creator_on_done", json={"enabled": True}),
            outsider.post(f"{team}/tasks/bulk-delete", json={"tasks": [{"id": task["id"]}]}),
        ]
        found = outsider.get(f"{BASE}/search", params={"q": "Shared"}).json()

    for response in responses:
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "WORKSPACE_NOT_FOUND"
    assert (found["workspaces"], found["projects"], found["tasks"]) == ([], [], [])
    assert company.clients["owner"].get(f"{BASE}/tasks/{task['id']}").status_code == 200
