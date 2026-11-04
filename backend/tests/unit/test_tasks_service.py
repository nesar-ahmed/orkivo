"""Unit tests for the tasks module (service rules, without HTTP)."""

import uuid
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.modules.tasks.enums import TaskPriority, TaskStatus
from app.modules.tasks.exceptions import TaskNotFoundError
from app.modules.tasks.schemas import TaskCreate, TaskUpdate
from app.modules.tasks.service import TaskService

pytestmark = pytest.mark.unit


@pytest.fixture()
def service(session: Session) -> TaskService:
    return TaskService(session)


def test_create_task_persists_with_defaults(service: TaskService) -> None:
    task = service.create_task(TaskCreate(title="Write baseline tests"))

    assert task.id is not None
    assert task.status == TaskStatus.TODO
    assert task.priority == TaskPriority.MEDIUM
    assert task.due_date is None
    assert task.created_at is not None and task.created_at.tzinfo is not None


def test_get_task_roundtrip(service: TaskService) -> None:
    created = service.create_task(
        TaskCreate(title="Plan release", priority="high", due_date=date(2026, 12, 1))
    )

    loaded = service.get_task(created.id)
    assert loaded.title == "Plan release"
    assert loaded.priority == TaskPriority.HIGH
    assert loaded.due_date == date(2026, 12, 1)


def test_get_missing_task_raises_domain_error(service: TaskService) -> None:
    with pytest.raises(TaskNotFoundError):
        service.get_task(uuid.uuid4())


def test_update_only_touches_supplied_fields(service: TaskService) -> None:
    task = service.create_task(TaskCreate(title="Draft spec", description="initial"))

    updated = service.update_task(task.id, TaskUpdate(status=TaskStatus.IN_PROGRESS))

    assert updated.status == TaskStatus.IN_PROGRESS
    assert updated.description == "initial"  # untouched field preserved
    assert updated.updated_at >= updated.created_at


def test_update_missing_task_raises(service: TaskService) -> None:
    with pytest.raises(TaskNotFoundError):
        service.update_task(uuid.uuid4(), TaskUpdate(title="ghost"))


def test_delete_removes_task(service: TaskService) -> None:
    task = service.create_task(TaskCreate(title="Remove me"))

    service.delete_task(task.id)

    with pytest.raises(TaskNotFoundError):
        service.get_task(task.id)


def test_list_paginates_and_reports_total(service: TaskService) -> None:
    for index in range(25):
        service.create_task(TaskCreate(title=f"Task {index:02d}"))

    items, total = service.list_tasks(page=2, page_size=10)

    assert total == 25
    assert len(items) == 10


def test_list_filters_by_status(service: TaskService) -> None:
    a = service.create_task(TaskCreate(title="Alpha"))
    service.create_task(TaskCreate(title="Beta"))
    service.update_task(a.id, TaskUpdate(status=TaskStatus.DONE))

    done_items, done_total = service.list_tasks(status=TaskStatus.DONE)
    todo_items, todo_total = service.list_tasks(status=TaskStatus.TODO)

    assert done_total == 1 and done_items[0].title == "Alpha"
    assert todo_total == 1 and todo_items[0].title == "Beta"


def test_list_search_is_case_insensitive_substring(service: TaskService) -> None:
    service.create_task(TaskCreate(title="Deploy pipeline"))
    service.create_task(TaskCreate(title="Review docs"))

    items, total = service.list_tasks(search="DEPLOY")

    assert total == 1
    assert items[0].title == "Deploy pipeline"


def test_search_wildcards_are_escaped(service: TaskService) -> None:
    service.create_task(TaskCreate(title="100% coverage"))
    service.create_task(TaskCreate(title="coverage plan"))

    # An unescaped "%" would act as a wildcard and match both tasks.
    # Escaping makes "% cov" a literal substring: only "100% coverage" hits.
    items, total = service.list_tasks(search="% cov")

    assert total == 1
    assert items[0].title == "100% coverage"
