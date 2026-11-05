"""Unit tests for the tasks module (service rules, without HTTP).

Tasks are always handled on behalf of an owner: the service takes the acting
user's id and never accepts an owner from the caller (architecture doc
section 9).
"""

import uuid
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.modules.tasks.enums import TaskPriority, TaskStatus
from app.modules.tasks.exceptions import TaskNotFoundError
from app.modules.tasks.schemas import TaskCreate, TaskUpdate
from app.modules.tasks.service import TaskService
from app.modules.users.models import User

pytestmark = pytest.mark.unit

OWNER = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER = uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture(autouse=True)
def owning_users(session: Session) -> None:
    """``tasks.owner_id`` is a real foreign key, so the owners must exist."""
    for user_id in (OWNER, OTHER):
        session.add(
            User(
                id=user_id,
                email=f"owner-{user_id.hex[:8]}@example.com",
                password_hash="synthetic-placeholder-not-a-credential",
                display_name="Fixture owner",
            )
        )
    session.commit()


@pytest.fixture()
def service(session: Session) -> TaskService:
    return TaskService(session)


def test_create_task_persists_with_defaults(service: TaskService) -> None:
    task = service.create_task(TaskCreate(title="Write baseline tests"), owner_id=OWNER)

    assert task.id is not None
    assert task.owner_id == OWNER
    assert task.status == TaskStatus.TODO
    assert task.priority == TaskPriority.MEDIUM
    assert task.due_date is None
    assert task.created_at is not None and task.created_at.tzinfo is not None


def test_get_task_roundtrip(service: TaskService) -> None:
    created = service.create_task(
        TaskCreate(title="Plan release", priority="high", due_date=date(2026, 12, 1)),
        owner_id=OWNER,
    )

    loaded = service.get_task(created.id, owner_id=OWNER)
    assert loaded.title == "Plan release"
    assert loaded.priority == TaskPriority.HIGH
    assert loaded.due_date == date(2026, 12, 1)


def test_get_missing_task_raises_domain_error(service: TaskService) -> None:
    with pytest.raises(TaskNotFoundError):
        service.get_task(uuid.uuid4(), owner_id=OWNER)


def test_task_owned_by_someone_else_reads_as_missing(service: TaskService) -> None:
    """Another user's task is indistinguishable from a nonexistent one."""
    task = service.create_task(TaskCreate(title="Private plan"), owner_id=OWNER)

    with pytest.raises(TaskNotFoundError):
        service.get_task(task.id, owner_id=OTHER)


def test_update_only_touches_supplied_fields(service: TaskService) -> None:
    task = service.create_task(
        TaskCreate(title="Draft spec", description="initial"), owner_id=OWNER
    )

    updated = service.update_task(
        task.id, TaskUpdate(status=TaskStatus.IN_PROGRESS), owner_id=OWNER
    )

    assert updated.status == TaskStatus.IN_PROGRESS
    assert updated.description == "initial"  # untouched field preserved
    assert updated.updated_at >= updated.created_at


def test_update_missing_task_raises(service: TaskService) -> None:
    with pytest.raises(TaskNotFoundError):
        service.update_task(uuid.uuid4(), TaskUpdate(title="ghost"), owner_id=OWNER)


def test_update_foreign_task_raises_and_leaves_owner(service: TaskService) -> None:
    task = service.create_task(TaskCreate(title="Not yours"), owner_id=OWNER)

    with pytest.raises(TaskNotFoundError):
        service.update_task(task.id, TaskUpdate(title="hijacked"), owner_id=OTHER)

    assert service.get_task(task.id, owner_id=OWNER).title == "Not yours"


def test_delete_removes_task(service: TaskService) -> None:
    task = service.create_task(TaskCreate(title="Remove me"), owner_id=OWNER)

    service.delete_task(task.id, owner_id=OWNER)

    with pytest.raises(TaskNotFoundError):
        service.get_task(task.id, owner_id=OWNER)


def test_delete_foreign_task_raises(service: TaskService) -> None:
    task = service.create_task(TaskCreate(title="Keep mine"), owner_id=OWNER)

    with pytest.raises(TaskNotFoundError):
        service.delete_task(task.id, owner_id=OTHER)

    assert service.get_task(task.id, owner_id=OWNER) is not None


def test_list_paginates_and_reports_total(service: TaskService) -> None:
    for index in range(25):
        service.create_task(TaskCreate(title=f"Task {index:02d}"), owner_id=OWNER)

    items, total = service.list_tasks(owner_id=OWNER, page=2, page_size=10)

    assert total == 25
    assert len(items) == 10


def test_list_returns_only_the_owners_tasks(service: TaskService) -> None:
    service.create_task(TaskCreate(title="Mine"), owner_id=OWNER)
    service.create_task(TaskCreate(title="Theirs"), owner_id=OTHER)

    items, total = service.list_tasks(owner_id=OWNER)

    assert total == 1
    assert [task.title for task in items] == ["Mine"]


def test_list_filters_by_status(service: TaskService) -> None:
    a = service.create_task(TaskCreate(title="Alpha"), owner_id=OWNER)
    service.create_task(TaskCreate(title="Beta"), owner_id=OWNER)
    service.update_task(a.id, TaskUpdate(status=TaskStatus.DONE), owner_id=OWNER)

    done_items, done_total = service.list_tasks(owner_id=OWNER, status=TaskStatus.DONE)
    todo_items, todo_total = service.list_tasks(owner_id=OWNER, status=TaskStatus.TODO)

    assert done_total == 1 and done_items[0].title == "Alpha"
    assert todo_total == 1 and todo_items[0].title == "Beta"


def test_list_search_is_case_insensitive_substring(service: TaskService) -> None:
    service.create_task(TaskCreate(title="Deploy pipeline"), owner_id=OWNER)
    service.create_task(TaskCreate(title="Review docs"), owner_id=OWNER)

    items, total = service.list_tasks(owner_id=OWNER, search="DEPLOY")

    assert total == 1
    assert items[0].title == "Deploy pipeline"


def test_search_wildcards_are_escaped(service: TaskService) -> None:
    service.create_task(TaskCreate(title="100% coverage"), owner_id=OWNER)
    service.create_task(TaskCreate(title="coverage plan"), owner_id=OWNER)

    # An unescaped "%" would act as a wildcard and match both tasks.
    # Escaping makes "% cov" a literal substring: only "100% coverage" hits.
    items, total = service.list_tasks(owner_id=OWNER, search="% cov")

    assert total == 1
    assert items[0].title == "100% coverage"
