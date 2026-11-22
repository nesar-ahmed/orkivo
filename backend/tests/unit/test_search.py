"""Unit tests for search across the caller's workspaces (service rules).

Search looks only where the caller may read --- the same tenants their own task
list spans --- so a result, or its absence, never says anything about another
company. The tests pin that scope, how matches rank, that what was typed is taken
literally, and how workspaces are matched (architecture doc sections 5 and 9).
"""

import pytest
from sqlalchemy.orm import Session

from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.projects.schemas import ProjectCreate
from app.modules.projects.service import ProjectService
from app.modules.search.service import SearchService
from app.modules.tasks.enums import TaskStatus
from app.modules.tasks.schemas import TaskCreate
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from app.modules.workspaces.enums import WorkspaceKind, WorkspaceRole
from app.modules.workspaces.schemas import InviteCreate, WorkspaceCreate
from app.modules.workspaces.service import WorkspaceService
from tests.synth import PASSWORD, email_for, slug_for

pytestmark = pytest.mark.unit


def _register(accounts: AuthService, label: str, name: str) -> User:
    return accounts.register(
        RegisterRequest(email=email_for(label), password=PASSWORD, display_name=name)
    )


class Cast:
    """Ana, in Acme with Olive; Oz, alone in his own company."""

    def __init__(self, session: Session) -> None:
        accounts = AuthService(session)
        self.workspaces = WorkspaceService(session)
        self.tasks = TaskService(session)
        self.projects = ProjectService(session)
        self.olive = _register(accounts, "find-olive", "Olive Owner")
        self.ana = _register(accounts, "find-ana", "Ana Member")
        self.oz = _register(accounts, "find-oz", "Oz Outsider")
        self.acme = self.workspaces.create_team(
            WorkspaceCreate(name="Acme Robotics", slug=slug_for("acme")), actor=self.olive
        )
        invite = self.workspaces.invite(
            self.acme.id,
            InviteCreate(user_id=self.ana.id, role=WorkspaceRole.MEMBER),
            actor=self.olive,
        )
        self.workspaces.accept_invitation(invite.id, actor=self.ana)
        self.elsewhere = self.workspaces.create_team(
            WorkspaceCreate(name="Launch Labs", slug=slug_for("elsewhere")), actor=self.oz
        )

    def task(self, title: str, *, by: User | None = None, **fields: object) -> None:
        actor = by or self.olive
        workspace = self.elsewhere.id if actor is self.oz else self.acme.id
        self.tasks.create_task(
            workspace, TaskCreate.model_validate({"title": title, **fields}), actor=actor
        )


@pytest.fixture()
def cast(session: Session) -> Cast:
    return Cast(session)


@pytest.fixture()
def search(session: Session) -> SearchService:
    return SearchService(session)


def titles(search: SearchService, term: str, actor: User, limit: int = 8) -> list[str]:
    return [task.title for task, _workspace in search.search(term, actor=actor, limit=limit).tasks]


def test_search_spans_the_callers_workspaces_and_nothing_else(
    cast: Cast, search: SearchService
) -> None:
    cast.task("Launch plan")
    private = cast.tasks.personal_workspace_id(actor=cast.ana)
    cast.tasks.create_task(private, TaskCreate(title="Launch party snacks"), actor=cast.ana)
    cast.task("Launch secrets", by=cast.oz)
    cast.projects.create_project(cast.acme.id, ProjectCreate(name="Launch site"), actor=cast.olive)

    results = search.search("launch", actor=cast.ana, limit=8)

    assert sorted(task.title for task, _ in results.tasks) == ["Launch party snacks", "Launch plan"]
    assert [(project.name, where.id) for project, where in results.projects] == [
        ("Launch site", cast.acme.id)
    ]
    # Oz's company is called "Launch Labs", and Ana is not in it.
    assert results.workspaces == []
    assert titles(search, "secrets", cast.ana) == []


def test_starting_with_the_term_beats_containing_it_and_open_beats_done(
    cast: Cast, search: SearchService
) -> None:
    cast.task("Fix the login page")
    cast.task("Login done", status=TaskStatus.DONE)
    cast.task("Relogin flow")
    cast.task("Login form")

    assert titles(search, "login", cast.ana) == [
        "Login form",  # starts with it, open
        "Login done",  # starts with it, done
        "Fix the login page",  # a word starts with it
        "Relogin flow",  # merely contains it
    ]


@pytest.mark.parametrize("term", ["%", "_", "100%"])
def test_what_was_typed_is_taken_literally(cast: Cast, search: SearchService, term: str) -> None:
    cast.task("Plain title")
    cast.task("Grow 100% faster")

    expected = ["Grow 100% faster"] if term in {"%", "100%"} else []
    assert titles(search, term, cast.ana) == expected


def test_workspaces_match_by_name_address_or_as_private(cast: Cast, search: SearchService) -> None:
    by_name = search.search("robot", actor=cast.ana, limit=8).workspaces
    by_slug = search.search(slug_for("acme"), actor=cast.ana, limit=8).workspaces
    private = search.search("private", actor=cast.ana, limit=8).workspaces

    assert [workspace.id for workspace in by_name] == [cast.acme.id]
    assert [workspace.id for workspace in by_slug] == [cast.acme.id]
    assert [workspace.kind for workspace in private] == [WorkspaceKind.PERSONAL]


def test_each_kind_is_capped_and_blank_terms_find_nothing(
    cast: Cast, search: SearchService
) -> None:
    for index in range(5):
        cast.task(f"Report {index}")

    assert len(titles(search, "report", cast.ana, limit=3)) == 3
    empty = search.search("   ", actor=cast.ana, limit=8)
    assert (empty.workspaces, empty.projects, empty.tasks) == ([], [], [])


def test_a_suspended_company_stays_searchable_until_you_leave(
    cast: Cast, search: SearchService
) -> None:
    cast.task("Frozen roadmap")
    cast.workspaces.set_suspended(cast.acme.id, suspended=True, note=None)

    assert titles(search, "roadmap", cast.ana) == ["Frozen roadmap"]

    cast.workspaces.set_suspended(cast.acme.id, suspended=False, note=None)
    cast.workspaces.remove_member(cast.acme.id, cast.ana.id, actor=cast.ana)
    assert titles(search, "roadmap", cast.ana) == []
