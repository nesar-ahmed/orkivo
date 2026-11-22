"""Unit tests for filing tasks under projects (service rules, without HTTP).

A task's project is one of *its own workspace's* projects, or none. The tests
below cover filing and moving a task, the project filter, and the ``project``
order that lets a paginated list be shown grouped by project (architecture doc
sections 6 and 9).
"""

import uuid
from collections.abc import Iterable
from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.projects.models import Project
from app.modules.projects.schemas import ProjectCreate
from app.modules.projects.service import ProjectService
from app.modules.tasks.enums import ProjectScope, TaskOrder
from app.modules.tasks.exceptions import ProjectNotInWorkspaceError, TaskConflictError
from app.modules.tasks.models import Task
from app.modules.tasks.schemas import TaskCreate, TaskUpdate
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from app.shared.time import utc_now
from tests.synth import PASSWORD, email_for

pytestmark = pytest.mark.unit


def _register(accounts: AuthService, label: str) -> User:
    return accounts.register(RegisterRequest(email=email_for(label), password=PASSWORD))


class Cast:
    """Two people with private workspaces, and projects in each."""

    def __init__(self, session: Session) -> None:
        accounts = AuthService(session)
        self.owner = _register(accounts, "filing-owner")
        self.other = _register(accounts, "filing-other")
        tasks = TaskService(session)
        projects = ProjectService(session)
        self.ws = tasks.personal_workspace_id(actor=self.owner)
        self.other_ws = tasks.personal_workspace_id(actor=self.other)

        def make(name: str, workspace: uuid.UUID, actor: User) -> Project:
            return projects.create_project(workspace, ProjectCreate(name=name), actor=actor)

        self.website = make("website", self.ws, self.owner)
        self.app = make("App", self.ws, self.owner)
        self.foreign = make("Theirs", self.other_ws, self.other)


@pytest.fixture()
def cast(session: Session) -> Cast:
    return Cast(session)


@pytest.fixture()
def service(session: Session) -> TaskService:
    return TaskService(session)


# --- filing ----------------------------------------------------------------
def test_a_task_can_be_created_in_a_project(service: TaskService, cast: Cast) -> None:
    task = service.create_task(
        cast.ws, TaskCreate(title="Hero banner", project_id=cast.website.id), actor=cast.owner
    )

    assert task.project_id == cast.website.id
    assert task.project is not None and task.project.name == "website"


def test_new_tasks_have_no_project_by_default(service: TaskService, cast: Cast) -> None:
    task = service.create_task(cast.ws, TaskCreate(title="Loose"), actor=cast.owner)

    assert task.project_id is None
    assert task.project is None


def test_another_workspaces_project_reads_exactly_like_a_missing_one(
    service: TaskService, cast: Cast, session: Session
) -> None:
    errors = []
    for candidate in (cast.foreign.id, uuid.uuid4()):
        with pytest.raises(ProjectNotInWorkspaceError) as raised:
            service.create_task(
                cast.ws, TaskCreate(title="Misfiled", project_id=candidate), actor=cast.owner
            )
        errors.append((raised.value.code, raised.value.message))

    assert errors[0] == errors[1]
    assert session.query(Task).filter_by(workspace_id=cast.ws).count() == 0


def test_moving_between_projects_returns_the_new_project_immediately(
    service: TaskService, cast: Cast
) -> None:
    task = service.create_task(
        cast.ws, TaskCreate(title="Mover", project_id=cast.website.id), actor=cast.owner
    )

    moved = service.update_task(task.id, TaskUpdate(project_id=cast.app.id), actor=cast.owner)

    assert moved.project_id == cast.app.id
    assert moved.project is not None and moved.project.name == "App"


def test_null_takes_a_task_out_of_its_project_and_omitting_it_keeps_it(
    service: TaskService, cast: Cast
) -> None:
    task = service.create_task(
        cast.ws, TaskCreate(title="Filed", project_id=cast.app.id), actor=cast.owner
    )

    kept = service.update_task(task.id, TaskUpdate(title="Still filed"), actor=cast.owner)
    assert kept.project_id == cast.app.id

    cleared = service.update_task(task.id, TaskUpdate(project_id=None), actor=cast.owner)
    assert cleared.project_id is None
    assert cleared.project is None


def test_moving_into_a_foreign_project_is_refused(service: TaskService, cast: Cast) -> None:
    task = service.create_task(cast.ws, TaskCreate(title="Stay home"), actor=cast.owner)

    with pytest.raises(ProjectNotInWorkspaceError):
        service.update_task(task.id, TaskUpdate(project_id=cast.foreign.id), actor=cast.owner)

    assert service.get_task(task.id, actor=cast.owner).project_id is None


def test_moving_with_a_stale_version_is_a_conflict(service: TaskService, cast: Cast) -> None:
    task = service.create_task(cast.ws, TaskCreate(title="Contested"), actor=cast.owner)
    seen = task.version
    service.update_task(task.id, TaskUpdate(title="Changed first"), actor=cast.owner)

    with pytest.raises(TaskConflictError):
        service.update_task(
            task.id, TaskUpdate(project_id=cast.app.id, version=seen), actor=cast.owner
        )


# --- filtering and ordering --------------------------------------------------
@pytest.fixture()
def spread(service: TaskService, cast: Cast, session: Session) -> None:
    """Tasks across both projects and none, created a minute apart, oldest first."""
    specs = [
        ("Web 1", cast.website.id),
        ("Loose 1", None),
        ("App 1", cast.app.id),
        ("Web 2", cast.website.id),
        ("Loose 2", None),
        ("App 2", cast.app.id),
    ]
    start = utc_now() - timedelta(hours=1)
    for index, (title, project_id) in enumerate(specs):
        task = service.create_task(
            cast.ws, TaskCreate(title=title, project_id=project_id), actor=cast.owner
        )
        # Distinct, increasing timestamps so "newest first" is unambiguous.
        task.created_at = start + timedelta(minutes=index)
    session.commit()


def titles(items: Iterable[Task]) -> list[str]:
    return [task.title for task in items]


def test_filter_by_a_project_and_by_none(service: TaskService, cast: Cast, spread: None) -> None:
    web, web_total = service.list_tasks(cast.ws, actor=cast.owner, project=cast.website.id)
    loose, _ = service.list_tasks(cast.ws, actor=cast.owner, project=ProjectScope.NONE)

    assert (titles(web), web_total) == (["Web 2", "Web 1"], 2)
    assert titles(loose) == ["Loose 2", "Loose 1"]


def test_filtering_by_a_foreign_project_finds_nothing(
    service: TaskService, cast: Cast, spread: None
) -> None:
    items, total = service.list_tasks(cast.ws, actor=cast.owner, project=cast.foreign.id)

    assert (list(items), total) == ([], 0)


def test_project_order_groups_alphabetically_with_no_project_last(
    service: TaskService, cast: Cast, spread: None
) -> None:
    """Case-insensitive: "App" sorts before "website"; newest first in each group."""
    items, total = service.list_tasks(cast.ws, actor=cast.owner, order=TaskOrder.PROJECT)

    assert total == 6
    assert titles(items) == ["App 2", "App 1", "Web 2", "Web 1", "Loose 2", "Loose 1"]


def test_project_order_pages_without_gaps_or_repeats(
    service: TaskService, cast: Cast, spread: None
) -> None:
    pages = [
        titles(
            service.list_tasks(
                cast.ws, actor=cast.owner, order=TaskOrder.PROJECT, page=page, page_size=4
            )[0]
        )
        for page in (1, 2)
    ]

    assert pages == [["App 2", "App 1", "Web 2", "Web 1"], ["Loose 2", "Loose 1"]]


def test_project_order_combines_with_filters(
    service: TaskService, cast: Cast, spread: None
) -> None:
    items, _ = service.list_tasks(cast.ws, actor=cast.owner, order=TaskOrder.PROJECT, search="2")

    assert titles(items) == ["App 2", "Web 2", "Loose 2"]
