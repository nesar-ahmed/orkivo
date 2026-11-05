"""Unit tests for the tasks module (service rules, without HTTP).

Tasks live in a workspace: the service takes the acting user and the tenant,
and access is the workspace policy's decision --- never an owner argument
accepted from the caller (architecture doc sections 6, 7 and 9). A task in
someone else's private workspace reads as not found, and members of a company
share its tasks whoever created them.

Fixtures register accounts the way the product does, so every actor here has
the personal workspace and membership row that a real caller always carries.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.tasks.enums import TaskPriority, TaskStatus
from app.modules.tasks.exceptions import TaskConflictError, TaskNotFoundError
from app.modules.tasks.schemas import TaskCreate, TaskUpdate
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from app.modules.workspaces.exceptions import WorkspaceNotFoundError
from tests.synth import PASSWORD, email_for

pytestmark = pytest.mark.unit


class Cast:
    """Two registered accounts, each with its own private workspace."""

    def __init__(self, session: Session) -> None:
        accounts = AuthService(session)
        self.owner = _register(accounts, "task-owner")
        self.other = _register(accounts, "task-other")
        tasks = TaskService(session)
        self.owner_ws = tasks.personal_workspace_id(actor=self.owner)
        self.other_ws = tasks.personal_workspace_id(actor=self.other)


def _register(accounts: AuthService, label: str) -> User:
    return accounts.register(RegisterRequest(email=email_for(label), password=PASSWORD))


@pytest.fixture()
def cast(session: Session) -> Cast:
    return Cast(session)


@pytest.fixture()
def service(session: Session) -> TaskService:
    return TaskService(session)


def test_create_task_persists_with_defaults(service: TaskService, cast: Cast) -> None:
    task = service.create_task(
        cast.owner_ws, TaskCreate(title="Write baseline tests"), actor=cast.owner
    )

    assert task.id is not None
    assert task.workspace_id == cast.owner_ws
    assert task.owner_id == cast.owner.id  # recorded from the actor, never the caller
    assert task.status == TaskStatus.TODO
    assert task.priority == TaskPriority.MEDIUM
    assert task.due_date is None
    assert task.created_at is not None and task.created_at.tzinfo is not None


def test_get_task_roundtrip(service: TaskService, cast: Cast) -> None:
    created = service.create_task(
        cast.owner_ws,
        TaskCreate(title="Plan release", priority="high", due_date=date(2026, 12, 1)),
        actor=cast.owner,
    )

    loaded = service.get_task(created.id, actor=cast.owner)
    assert loaded.title == "Plan release"
    assert loaded.priority == TaskPriority.HIGH
    assert loaded.due_date == date(2026, 12, 1)


def test_get_missing_task_raises_domain_error(service: TaskService, cast: Cast) -> None:
    with pytest.raises(TaskNotFoundError):
        service.get_task(uuid.uuid4(), actor=cast.owner)


def test_task_in_another_tenant_reads_as_missing(service: TaskService, cast: Cast) -> None:
    """A task in someone else's private workspace is indistinguishable from a
    nonexistent one."""
    task = service.create_task(cast.owner_ws, TaskCreate(title="Private plan"), actor=cast.owner)

    with pytest.raises(TaskNotFoundError):
        service.get_task(task.id, actor=cast.other)


def test_update_only_touches_supplied_fields(service: TaskService, cast: Cast) -> None:
    task = service.create_task(
        cast.owner_ws,
        TaskCreate(title="Draft spec", description="initial"),
        actor=cast.owner,
    )

    updated = service.update_task(
        task.id, TaskUpdate(status=TaskStatus.IN_PROGRESS), actor=cast.owner
    )

    assert updated.status == TaskStatus.IN_PROGRESS
    assert updated.description == "initial"  # untouched field preserved
    assert updated.updated_by_id == cast.owner.id
    assert updated.updated_at >= updated.created_at


def test_update_missing_task_raises(service: TaskService, cast: Cast) -> None:
    with pytest.raises(TaskNotFoundError):
        service.update_task(uuid.uuid4(), TaskUpdate(title="ghost"), actor=cast.owner)


def test_update_foreign_task_raises_and_leaves_owner(service: TaskService, cast: Cast) -> None:
    task = service.create_task(cast.owner_ws, TaskCreate(title="Not yours"), actor=cast.owner)

    with pytest.raises(TaskNotFoundError):
        service.update_task(task.id, TaskUpdate(title="hijacked"), actor=cast.other)

    assert service.get_task(task.id, actor=cast.owner).title == "Not yours"


def test_update_with_stale_version_raises_conflict(service: TaskService, cast: Cast) -> None:
    """Optimistic concurrency: sending a version older than the row's refuses
    the write instead of silently undoing the newer change."""
    task = service.create_task(cast.owner_ws, TaskCreate(title="Shared edit"), actor=cast.owner)
    created_version = task.version
    updated = service.update_task(task.id, TaskUpdate(title="First edit"), actor=cast.owner)
    assert updated.version == created_version + 1

    with pytest.raises(TaskConflictError):
        service.update_task(task.id, TaskUpdate(title="Stale edit", version=1), actor=cast.owner)

    assert service.get_task(task.id, actor=cast.owner).title == "First edit"


def test_delete_removes_task(service: TaskService, cast: Cast) -> None:
    task = service.create_task(cast.owner_ws, TaskCreate(title="Remove me"), actor=cast.owner)

    service.delete_task(task.id, actor=cast.owner)

    with pytest.raises(TaskNotFoundError):
        service.get_task(task.id, actor=cast.owner)


def test_delete_foreign_task_raises(service: TaskService, cast: Cast) -> None:
    task = service.create_task(cast.owner_ws, TaskCreate(title="Keep mine"), actor=cast.owner)

    with pytest.raises(TaskNotFoundError):
        service.delete_task(task.id, actor=cast.other)

    assert service.get_task(task.id, actor=cast.owner) is not None


def test_delete_with_stale_version_raises_conflict(service: TaskService, cast: Cast) -> None:
    task = service.create_task(cast.owner_ws, TaskCreate(title="Racing delete"), actor=cast.owner)

    with pytest.raises(TaskConflictError):
        service.delete_task(task.id, actor=cast.owner, version=task.version + 1)

    assert service.get_task(task.id, actor=cast.owner) is not None


def test_list_paginates_and_reports_total(service: TaskService, cast: Cast) -> None:
    for index in range(25):
        service.create_task(cast.owner_ws, TaskCreate(title=f"Task {index:02d}"), actor=cast.owner)

    items, total = service.list_tasks(cast.owner_ws, actor=cast.owner, page=2, page_size=10)

    assert total == 25
    assert len(items) == 10


def test_list_returns_only_the_workspaces_tasks(service: TaskService, cast: Cast) -> None:
    service.create_task(cast.owner_ws, TaskCreate(title="Mine"), actor=cast.owner)
    service.create_task(cast.other_ws, TaskCreate(title="Theirs"), actor=cast.other)

    items, total = service.list_tasks(cast.owner_ws, actor=cast.owner)

    assert total == 1
    assert [task.title for task in items] == ["Mine"]


def test_list_from_outside_the_tenant_raises_not_found(service: TaskService, cast: Cast) -> None:
    """The collection route is addressed by workspace, so an outsider is refused
    by the policy's tenant-not-found shape before any task query runs."""
    service.create_task(cast.owner_ws, TaskCreate(title="Private"), actor=cast.owner)

    with pytest.raises(WorkspaceNotFoundError):
        service.list_tasks(cast.owner_ws, actor=cast.other)


def test_list_filters_by_status(service: TaskService, cast: Cast) -> None:
    a = service.create_task(cast.owner_ws, TaskCreate(title="Alpha"), actor=cast.owner)
    service.create_task(cast.owner_ws, TaskCreate(title="Beta"), actor=cast.owner)
    service.update_task(a.id, TaskUpdate(status=TaskStatus.DONE), actor=cast.owner)

    done_items, done_total = service.list_tasks(
        cast.owner_ws, actor=cast.owner, status=TaskStatus.DONE
    )
    todo_items, todo_total = service.list_tasks(
        cast.owner_ws, actor=cast.owner, status=TaskStatus.TODO
    )

    assert done_total == 1 and done_items[0].title == "Alpha"
    assert todo_total == 1 and todo_items[0].title == "Beta"


def test_list_search_is_case_insensitive_substring(service: TaskService, cast: Cast) -> None:
    service.create_task(cast.owner_ws, TaskCreate(title="Deploy pipeline"), actor=cast.owner)
    service.create_task(cast.owner_ws, TaskCreate(title="Review docs"), actor=cast.owner)

    items, total = service.list_tasks(cast.owner_ws, actor=cast.owner, search="DEPLOY")

    assert total == 1
    assert items[0].title == "Deploy pipeline"


def test_search_wildcards_are_escaped(service: TaskService, cast: Cast) -> None:
    service.create_task(cast.owner_ws, TaskCreate(title="100% coverage"), actor=cast.owner)
    service.create_task(cast.owner_ws, TaskCreate(title="coverage plan"), actor=cast.owner)

    # An unescaped "%" would act as a wildcard and match both tasks.
    # Escaping makes "% cov" a literal substring: only "100% coverage" hits.
    items, total = service.list_tasks(cast.owner_ws, actor=cast.owner, search="% cov")

    assert total == 1
    assert items[0].title == "100% coverage"
