"""Unit tests for changing and deleting several tasks at once (service rules).

A bulk request is the same save as a single one, once per task, in one
transaction: each task is held to the same rule, gets its own activity event and
tells the same people. It is all or nothing --- a refusal names every task that
caused it, and leaves every task as it was (architecture doc sections 6.2 and 9).

Accounts join companies the way the product does --- invite, then accept --- so
no test relies on a membership state a real caller could not reach.
"""

import uuid
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.activity.enums import ActivityVerb
from app.modules.activity.models import ActivityEvent
from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.labels.enums import LabelColor
from app.modules.labels.models import Label
from app.modules.labels.schemas import LabelCreate
from app.modules.labels.service import LabelService
from app.modules.notifications.enums import NotificationKind
from app.modules.notifications.models import Notification
from app.modules.task_dependencies.schemas import DependencyCreate
from app.modules.task_dependencies.service import TaskDependencyService
from app.modules.tasks import schemas as task_schemas
from app.modules.tasks.enums import TaskPriority, TaskStatus
from app.modules.tasks.exceptions import (
    AssigneeNotMemberError,
    BulkTaskConflictError,
    BulkTaskForbiddenError,
    TaskLabelLimitError,
    TaskNotFoundError,
)
from app.modules.tasks.models import Task
from app.modules.tasks.schemas import (
    BulkTaskChanges,
    BulkTaskDelete,
    BulkTaskRef,
    BulkTaskUpdate,
    TaskCreate,
    TaskUpdate,
)
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from app.modules.workspaces.enums import WorkspaceRole
from app.modules.workspaces.exceptions import (
    WorkspaceNotFoundError,
    WorkspaceRoleNotAllowedError,
    WorkspaceSuspendedError,
)
from app.modules.workspaces.schemas import InviteCreate, WorkspaceCreate
from app.modules.workspaces.service import WorkspaceService
from tests.synth import PASSWORD, email_for, slug_for

pytestmark = pytest.mark.unit


def _register(accounts: AuthService, label: str, name: str) -> User:
    return accounts.register(
        RegisterRequest(email=email_for(label), password=PASSWORD, display_name=name)
    )


class Cast:
    """A company with an owner, a manager, two members and a viewer; an outsider."""

    def __init__(self, session: Session) -> None:
        accounts = AuthService(session)
        self.session = session
        self.workspaces = WorkspaceService(session)
        self.tasks = TaskService(session)
        self.owner = _register(accounts, "bulk-owner", "Olive Owner")
        self.manager = _register(accounts, "bulk-manager", "Max Manager")
        self.member = _register(accounts, "bulk-member", "Mo Member")
        self.colleague = _register(accounts, "bulk-colleague", "Cy Colleague")
        self.viewer = _register(accounts, "bulk-viewer", "Vi Viewer")
        self.outsider = _register(accounts, "bulk-outsider", "Oz Outsider")
        self.team = self.workspaces.create_team(
            WorkspaceCreate(name="Bulk Co", slug=slug_for("bulk")), actor=self.owner
        )
        for account, role in (
            (self.manager, WorkspaceRole.MANAGER),
            (self.member, WorkspaceRole.MEMBER),
            (self.colleague, WorkspaceRole.MEMBER),
            (self.viewer, WorkspaceRole.VIEWER),
        ):
            invite = self.workspaces.invite(
                self.team.id, InviteCreate(user_id=account.id, role=role), actor=self.owner
            )
            self.workspaces.accept_invitation(invite.id, actor=account)

    def task(self, title: str, *, by: User | None = None, **fields: Any) -> Task:
        return self.tasks.create_task(
            self.team.id,
            TaskCreate.model_validate({"title": title, **fields}),
            actor=by or self.owner,
        )

    def label(self, name: str) -> Label:
        return LabelService(self.session).create_label(
            self.team.id, LabelCreate(name=name, color=LabelColor.RED), actor=self.owner
        )


@pytest.fixture()
def cast(session: Session) -> Cast:
    return Cast(session)


def refs(*tasks: Task, versions: bool = True) -> list[BulkTaskRef]:
    return [BulkTaskRef(id=task.id, version=task.version if versions else None) for task in tasks]


def update(cast: Cast, tasks: list[BulkTaskRef], actor: User, **changes: Any) -> list[Task]:
    return cast.tasks.bulk_update(
        cast.team.id,
        BulkTaskUpdate(tasks=tasks, changes=BulkTaskChanges.model_validate(changes)),
        actor=actor,
    )


def events(session: Session, task: Task) -> list[ActivityEvent]:
    return list(
        session.scalars(
            select(ActivityEvent)
            .where(ActivityEvent.task_id == task.id)
            .order_by(ActivityEvent.created_at, ActivityEvent.id)
        )
    )


def notified(session: Session, person: User, kind: NotificationKind) -> list[uuid.UUID]:
    return list(
        session.scalars(
            select(Notification.task_id).where(
                Notification.recipient_id == person.id, Notification.kind == kind
            )
        )
    )


def titles_and_versions(cast: Cast, *tasks: Task) -> list[tuple[str, int]]:
    return [
        (loaded.title, loaded.version)
        for loaded in (cast.tasks.get_task(task.id, actor=cast.owner) for task in tasks)
    ]


# --- changing several tasks ------------------------------------------------------
def test_one_change_saves_every_task_as_its_own_edit(cast: Cast, session: Session) -> None:
    mine = cast.task("Mine", by=cast.member)
    theirs = cast.task("Theirs", by=cast.colleague)

    changed = update(
        cast,
        refs(theirs, mine),
        cast.manager,
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
    )

    assert [task.id for task in changed] == [theirs.id, mine.id]  # the request's order
    for task in changed:
        assert (task.status, task.priority, task.version) == (
            TaskStatus.IN_PROGRESS,
            TaskPriority.HIGH,
            2,
        )
        assert task.updated_by_id == cast.manager.id
        last = events(session, task)[-1]
        assert last.verb is ActivityVerb.TASK_UPDATED
        assert last.actor_id == cast.manager.id
        assert last.changes == {
            "status": {"from": "todo", "to": "in_progress"},
            "priority": {"from": "medium", "to": "high"},
        }


def test_null_clears_a_field_and_unchanged_tasks_say_nothing(cast: Cast, session: Session) -> None:
    dated = cast.task("Dated", due_date="2026-11-20")
    plain = cast.task("Plain")

    update(cast, refs(dated, plain), cast.owner, due_date=None)

    assert cast.tasks.get_task(dated.id, actor=cast.owner).due_date is None
    # Saving a value a task already had changes nothing, and records nothing.
    assert [event.verb for event in events(session, plain)] == [ActivityVerb.TASK_CREATED]


def test_labels_are_added_and_removed_without_touching_the_others(cast: Cast) -> None:
    bug, docs, urgent = cast.label("Bug"), cast.label("Docs"), cast.label("Urgent")
    first = cast.task("First", label_ids=[docs.id])
    second = cast.task("Second", label_ids=[bug.id, urgent.id])

    changed = update(
        cast, refs(first, second), cast.owner, add_label_ids=[bug.id], remove_label_ids=[urgent.id]
    )

    assert [[label.name for label in task.labels] for task in changed] == [
        ["Bug", "Docs"],
        ["Bug"],
    ]


def test_a_label_that_would_overfill_a_task_refuses_the_whole_request(
    cast: Cast, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.modules.tasks.service.MAX_LABELS_PER_TASK", 1)
    bug, docs = cast.label("Bug"), cast.label("Docs")
    roomy = cast.task("Roomy")
    full = cast.task("Full", label_ids=[docs.id])

    with pytest.raises(TaskLabelLimitError) as refused:
        update(cast, refs(roomy, full), cast.owner, add_label_ids=[bug.id])

    assert [detail.field for detail in refused.value.details] == ["tasks.1.id"]
    assert cast.tasks.get_task(roomy.id, actor=cast.owner).labels == []


def test_bulk_assigning_tells_the_assignee_once_per_task(cast: Cast, session: Session) -> None:
    first, second = cast.task("First"), cast.task("Second")

    update(cast, refs(first, second), cast.owner, assignee_id=cast.member.id)

    assert sorted(notified(session, cast.member, NotificationKind.ASSIGNED), key=str) == sorted(
        [first.id, second.id], key=str
    )


def test_an_assignee_from_outside_the_workspace_is_refused(cast: Cast) -> None:
    task = cast.task("Task")

    with pytest.raises(AssigneeNotMemberError):
        update(cast, refs(task), cast.owner, assignee_id=cast.outsider.id)


def test_finishing_blockers_in_bulk_tells_who_is_ready_to_start(
    cast: Cast, session: Session
) -> None:
    launch = cast.task("Launch", assignee_id=cast.member.id)
    copy, design = cast.task("Copy"), cast.task("Design")
    dependencies = TaskDependencyService(session)
    for blocker in (copy, design):
        dependencies.add_blocker(
            launch.id, DependencyCreate(blocking_task_id=blocker.id), actor=cast.owner
        )

    update(cast, refs(copy, design), cast.owner, status=TaskStatus.DONE)

    assert notified(session, cast.member, NotificationKind.UNBLOCKED) == [launch.id]


# --- all or nothing ----------------------------------------------------------------
def test_a_member_is_refused_for_every_task_that_is_not_theirs(cast: Cast) -> None:
    mine = cast.task("Mine", by=cast.member)
    held = cast.task("Held", assignee_id=cast.member.id)
    theirs = cast.task("Theirs", by=cast.colleague)
    others = cast.task("Others")

    with pytest.raises(BulkTaskForbiddenError) as refused:
        update(cast, refs(mine, theirs, held, others), cast.member, priority=TaskPriority.LOW)

    assert refused.value.code == "TASK_FORBIDDEN"
    assert [detail.field for detail in refused.value.details] == ["tasks.1.id", "tasks.3.id"]
    assert titles_and_versions(cast, mine, held) == [("Mine", 1), ("Held", 1)]


def test_stale_versions_are_named_and_nothing_changes(cast: Cast) -> None:
    fresh, stale = cast.task("Fresh"), cast.task("Stale")
    seen = refs(fresh, stale)
    cast.tasks.update_task(stale.id, TaskUpdate(title="Changed meanwhile"), actor=cast.manager)

    with pytest.raises(BulkTaskConflictError) as refused:
        update(cast, seen, cast.owner, priority=TaskPriority.LOW)

    assert [detail.field for detail in refused.value.details] == ["tasks.1.version"]
    assert cast.tasks.get_task(fresh.id, actor=cast.owner).priority is TaskPriority.MEDIUM


def test_omitting_versions_is_last_write_wins(cast: Cast) -> None:
    task = cast.task("Contested")
    cast.tasks.update_task(task.id, TaskUpdate(title="Changed meanwhile"), actor=cast.manager)

    (changed,) = update(cast, refs(task, versions=False), cast.owner, priority=TaskPriority.LOW)

    assert (changed.title, changed.priority) == ("Changed meanwhile", TaskPriority.LOW)


def test_a_task_from_another_workspace_reads_as_missing(cast: Cast) -> None:
    here = cast.task("Here")
    private = cast.tasks.personal_workspace_id(actor=cast.owner)
    elsewhere = cast.tasks.create_task(private, TaskCreate(title="Private"), actor=cast.owner)

    with pytest.raises(TaskNotFoundError):
        update(cast, refs(here, elsewhere), cast.owner, priority=TaskPriority.LOW)

    assert cast.tasks.get_task(here.id, actor=cast.owner).version == 1


def test_roles_and_suspension_are_refused_before_any_task_is_read(cast: Cast) -> None:
    task = cast.task("Task")

    with pytest.raises(WorkspaceRoleNotAllowedError):
        update(cast, refs(task), cast.viewer, priority=TaskPriority.LOW)
    with pytest.raises(WorkspaceNotFoundError):
        update(cast, refs(task), cast.outsider, priority=TaskPriority.LOW)

    cast.workspaces.set_suspended(cast.team.id, suspended=True, note=None)
    with pytest.raises(WorkspaceSuspendedError):
        update(cast, refs(task), cast.owner, priority=TaskPriority.LOW)


# --- deleting several tasks ----------------------------------------------------------
def test_bulk_delete_records_each_task_by_name(cast: Cast, session: Session) -> None:
    first, second = cast.task("First"), cast.task("Second")

    cast.tasks.bulk_delete(
        cast.team.id, BulkTaskDelete(tasks=refs(first, second)), actor=cast.manager
    )

    for task, title in ((first, "First"), (second, "Second")):
        with pytest.raises(TaskNotFoundError):
            cast.tasks.get_task(task.id, actor=cast.owner)
        deleted = events(session, task)[-1]
        assert (deleted.verb, deleted.task_title, deleted.actor_id) == (
            ActivityVerb.TASK_DELETED,
            title,
            cast.manager.id,
        )


def test_a_member_deletes_only_tasks_they_created(cast: Cast) -> None:
    mine = cast.task("Mine", by=cast.member)
    held = cast.task("Held", assignee_id=cast.member.id)

    with pytest.raises(BulkTaskForbiddenError) as refused:
        cast.tasks.bulk_delete(
            cast.team.id, BulkTaskDelete(tasks=refs(mine, held)), actor=cast.member
        )

    assert [detail.field for detail in refused.value.details] == ["tasks.1.id"]
    assert cast.tasks.get_task(mine.id, actor=cast.member).title == "Mine"

    cast.tasks.bulk_delete(cast.team.id, BulkTaskDelete(tasks=refs(mine)), actor=cast.member)
    with pytest.raises(TaskNotFoundError):
        cast.tasks.get_task(mine.id, actor=cast.member)


# --- the contract ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "body",
    [
        {"tasks": [], "changes": {"status": "done"}},
        {
            "tasks": [{"id": "00000000-0000-0000-0000-000000000001"}] * 2,
            "changes": {"status": "done"},
        },
        {"tasks": [{"id": "00000000-0000-0000-0000-000000000001"}], "changes": {}},
        {"tasks": [{"id": "00000000-0000-0000-0000-000000000001"}], "changes": {"status": None}},
        {
            "tasks": [{"id": "00000000-0000-0000-0000-000000000001"}],
            "changes": {
                "add_label_ids": ["00000000-0000-0000-0000-0000000000aa"],
                "remove_label_ids": ["00000000-0000-0000-0000-0000000000aa"],
            },
        },
    ],
    ids=["no-tasks", "a-task-twice", "no-change", "status-cleared", "label-both-ways"],
)
def test_malformed_bulk_requests_are_refused_by_the_contract(body: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        BulkTaskUpdate.model_validate(body)


def test_a_request_holds_at_most_a_page_of_tasks() -> None:
    too_many = [{"id": str(uuid.uuid4())} for _ in range(task_schemas.MAX_BULK_TASKS + 1)]

    with pytest.raises(ValidationError):
        BulkTaskDelete.model_validate({"tasks": too_many})
