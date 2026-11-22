"""Unit tests for task dependencies (service rules, without HTTP).

A task can wait on other tasks of its own workspace. Four rules keep the links
meaningful --- same workspace, never itself, never twice, never a loop --- and
each has tests below, as do the change rule it inherits from its task, what the
activity log says, the open-blocker counts every task response carries, and the
"ready to start" notification when the last open blocker is done
(architecture doc sections 6 and 9).
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.activity.enums import ActivityVerb
from app.modules.activity.models import ActivityEvent
from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.notifications.enums import NotificationKind
from app.modules.notifications.models import Notification
from app.modules.task_dependencies import service as dependency_service
from app.modules.task_dependencies.exceptions import (
    DependencyCycleError,
    DependencyExistsError,
    DependencyLimitReachedError,
    DependencyNotFoundError,
    DependencyNotInWorkspaceError,
    SelfDependencyError,
)
from app.modules.task_dependencies.models import TaskDependency
from app.modules.task_dependencies.schemas import DependencyCreate
from app.modules.task_dependencies.service import TaskDependencyService
from app.modules.tasks.enums import TaskStatus
from app.modules.tasks.exceptions import (
    TaskConflictError,
    TaskForbiddenError,
    TaskNotFoundError,
)
from app.modules.tasks.models import Task
from app.modules.tasks.schemas import TaskCreate, TaskUpdate
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from app.modules.workspaces.enums import WorkspaceRole
from app.modules.workspaces.exceptions import (
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
    """A company with an owner, a manager, a member and a viewer, and an outsider
    with their own. Tasks are the owner's unless a test gives them to someone."""

    def __init__(self, session: Session) -> None:
        accounts = AuthService(session)
        self.workspaces = WorkspaceService(session)
        self.tasks = TaskService(session)
        self.owner = _register(accounts, "deps-owner", "Olive Owner")
        self.manager = _register(accounts, "deps-manager", "Max Manager")
        self.member = _register(accounts, "deps-member", "Mo Member")
        self.viewer = _register(accounts, "deps-viewer", "Vi Viewer")
        self.outsider = _register(accounts, "deps-outsider", "Oz Outsider")
        self.team = self.workspaces.create_team(
            WorkspaceCreate(name="Deps Co", slug=slug_for("deps")), actor=self.owner
        )
        for account, role in (
            (self.manager, WorkspaceRole.MANAGER),
            (self.member, WorkspaceRole.MEMBER),
            (self.viewer, WorkspaceRole.VIEWER),
        ):
            invite = self.workspaces.invite(
                self.team.id, InviteCreate(user_id=account.id, role=role), actor=self.owner
            )
            self.workspaces.accept_invitation(invite.id, actor=account)
        self.elsewhere = self.workspaces.create_team(
            WorkspaceCreate(name="Elsewhere Co", slug=slug_for("deps-elsewhere")),
            actor=self.outsider,
        )

    def task(self, title: str, **fields: object) -> Task:
        return self.tasks.create_task(
            self.team.id,
            TaskCreate.model_validate({"title": title, **fields}),
            actor=self.owner,
        )


@pytest.fixture()
def cast(session: Session) -> Cast:
    return Cast(session)


@pytest.fixture()
def service(session: Session) -> TaskDependencyService:
    return TaskDependencyService(session)


def block(service: TaskDependencyService, waiting: Task, on: Task, actor: User) -> None:
    service.add_blocker(waiting.id, DependencyCreate(blocking_task_id=on.id), actor=actor)


def titles(tasks: list[Task]) -> list[str]:
    return [task.title for task in tasks]


# --- linking ----------------------------------------------------------------
def test_a_member_links_a_task_they_hold_and_both_sides_see_it(
    service: TaskDependencyService, cast: Cast
) -> None:
    launch = cast.task("Launch", assignee_id=cast.member.id)
    copy, design = cast.task("Write copy"), cast.task("Design")

    shown = service.add_blocker(
        launch.id, DependencyCreate(blocking_task_id=copy.id), actor=cast.member
    )
    block(service, launch, design, cast.member)

    assert titles(shown.blocked_by) == ["Write copy"]
    assert titles(service.dependencies_of(launch.id, actor=cast.owner).blocked_by) == [
        "Design",
        "Write copy",
    ]
    assert titles(service.dependencies_of(copy.id, actor=cast.owner).blocking) == ["Launch"]


def test_open_work_is_listed_before_finished_work(
    service: TaskDependencyService, cast: Cast
) -> None:
    launch = cast.task("Launch")
    block(service, launch, cast.task("Alpha, done", status=TaskStatus.DONE), cast.owner)
    block(service, launch, cast.task("Zulu, open"), cast.owner)

    assert titles(service.dependencies_of(launch.id, actor=cast.owner).blocked_by) == [
        "Zulu, open",
        "Alpha, done",
    ]


def test_a_task_cannot_wait_on_itself(service: TaskDependencyService, cast: Cast) -> None:
    task = cast.task("Loop")

    with pytest.raises(SelfDependencyError):
        block(service, task, task, cast.owner)


def test_a_task_from_elsewhere_reads_exactly_like_a_missing_one(
    service: TaskDependencyService, cast: Cast
) -> None:
    launch = cast.task("Launch")
    theirs = cast.tasks.create_task(
        cast.elsewhere.id, TaskCreate(title="Theirs"), actor=cast.outsider
    )

    answers = []
    for candidate in (theirs.id, uuid.uuid4()):
        with pytest.raises(DependencyNotInWorkspaceError) as refused:
            service.add_blocker(
                launch.id, DependencyCreate(blocking_task_id=candidate), actor=cast.owner
            )
        answers.append((refused.value.code, refused.value.message))

    assert answers[0] == answers[1]


def test_the_same_link_twice_is_refused(service: TaskDependencyService, cast: Cast) -> None:
    launch, copy = cast.task("Launch"), cast.task("Copy")
    block(service, launch, copy, cast.owner)

    with pytest.raises(DependencyExistsError):
        block(service, launch, copy, cast.manager)


def test_a_direct_loop_is_refused(service: TaskDependencyService, cast: Cast) -> None:
    a, b = cast.task("A"), cast.task("B")
    block(service, b, a, cast.owner)  # B waits on A

    with pytest.raises(DependencyCycleError):
        block(service, a, b, cast.owner)  # A waits on B: a loop


def test_a_loop_through_several_tasks_is_refused(
    service: TaskDependencyService, cast: Cast
) -> None:
    a, b, c, d = (cast.task(name) for name in "ABCD")
    block(service, b, a, cast.owner)  # A, then B
    block(service, c, b, cast.owner)  # then C
    block(service, d, c, cast.owner)  # then D

    with pytest.raises(DependencyCycleError):
        block(service, a, d, cast.owner)  # A waits on D, which waits on A


def test_a_diamond_is_not_a_loop(service: TaskDependencyService, cast: Cast) -> None:
    """Two paths to the same task are fine; only a way back is a loop."""
    start, left, right, end = (cast.task(name) for name in ("Start", "Left", "Right", "End"))
    block(service, left, start, cast.owner)
    block(service, right, start, cast.owner)
    block(service, end, left, cast.owner)

    block(service, end, right, cast.owner)

    assert titles(service.dependencies_of(end.id, actor=cast.owner).blocked_by) == [
        "Left",
        "Right",
    ]


def test_a_task_waits_on_a_bounded_number_of_tasks(
    service: TaskDependencyService, cast: Cast, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dependency_service, "MAX_BLOCKERS_PER_TASK", 2)
    launch = cast.task("Launch")
    block(service, launch, cast.task("One"), cast.owner)
    block(service, launch, cast.task("Two"), cast.owner)

    with pytest.raises(DependencyLimitReachedError) as refused:
        block(service, launch, cast.task("Three"), cast.owner)
    assert "2 tasks" in refused.value.message


def test_removing_a_link(service: TaskDependencyService, cast: Cast) -> None:
    launch, copy = cast.task("Launch", assignee_id=cast.member.id), cast.task("Copy")
    block(service, launch, copy, cast.owner)

    service.remove_blocker(launch.id, copy.id, actor=cast.member)

    assert service.dependencies_of(launch.id, actor=cast.owner).blocked_by == []
    with pytest.raises(DependencyNotFoundError):
        service.remove_blocker(launch.id, copy.id, actor=cast.member)


def test_deleting_a_task_removes_its_links_both_ways(
    service: TaskDependencyService, cast: Cast, session: Session
) -> None:
    first, middle, last = cast.task("First"), cast.task("Middle"), cast.task("Last")
    block(service, middle, first, cast.owner)
    block(service, last, middle, cast.owner)

    cast.tasks.delete_task(middle.id, actor=cast.owner)

    assert session.scalars(select(TaskDependency)).all() == []
    assert service.dependencies_of(last.id, actor=cast.owner).blocked_by == []


# --- access -----------------------------------------------------------------
def test_only_who_may_change_the_waiting_task_may_link_it(
    service: TaskDependencyService, cast: Cast
) -> None:
    """Planning a task is changing it: the blocking task only has to be readable."""
    theirs, mine = cast.task("Theirs"), cast.task("Mine", assignee_id=cast.member.id)
    copy = cast.task("Copy")

    with pytest.raises(TaskForbiddenError):
        block(service, theirs, copy, cast.member)
    with pytest.raises(WorkspaceRoleNotAllowedError):
        block(service, mine, copy, cast.viewer)
    block(service, mine, theirs, cast.member)  # waiting on someone else's task is fine
    block(service, theirs, copy, cast.manager)
    with pytest.raises(TaskForbiddenError):
        service.remove_blocker(theirs.id, copy.id, actor=cast.member)

    assert titles(service.dependencies_of(theirs.id, actor=cast.viewer).blocked_by) == ["Copy"]
    assert titles(service.dependencies_of(mine.id, actor=cast.viewer).blocked_by) == ["Theirs"]


def test_outsiders_read_a_linked_task_as_missing(
    service: TaskDependencyService, cast: Cast
) -> None:
    launch, copy = cast.task("Launch"), cast.task("Copy")

    for attempt in (
        lambda: service.dependencies_of(launch.id, actor=cast.outsider),
        lambda: block(service, launch, copy, cast.outsider),
        lambda: service.remove_blocker(launch.id, copy.id, actor=cast.outsider),
    ):
        with pytest.raises(TaskNotFoundError):
            attempt()


def test_a_suspended_company_keeps_its_dependencies_readable_and_frozen(
    service: TaskDependencyService, cast: Cast
) -> None:
    launch, copy, other = cast.task("Launch"), cast.task("Copy"), cast.task("Other")
    block(service, launch, copy, cast.owner)
    cast.workspaces.set_suspended(cast.team.id, suspended=True, note=None)

    assert titles(service.dependencies_of(launch.id, actor=cast.member).blocked_by) == ["Copy"]
    for attempt in (
        lambda: block(service, launch, other, cast.owner),
        lambda: service.remove_blocker(launch.id, copy.id, actor=cast.owner),
    ):
        with pytest.raises(WorkspaceSuspendedError):
            attempt()


# --- history and versions -----------------------------------------------------
def test_linking_is_recorded_on_the_waiting_task_without_a_new_version(
    service: TaskDependencyService, cast: Cast, session: Session
) -> None:
    launch, copy = cast.task("Launch", assignee_id=cast.member.id), cast.task("Write copy")
    version = launch.version

    block(service, launch, copy, cast.member)
    service.remove_blocker(launch.id, copy.id, actor=cast.owner)

    events = session.scalars(
        select(ActivityEvent)
        .where(ActivityEvent.task_id == launch.id)
        .order_by(ActivityEvent.created_at, ActivityEvent.id)
    ).all()
    ref = {"id": str(copy.id), "name": "Write copy"}
    assert [(event.verb, event.changes) for event in events[1:]] == [
        (ActivityVerb.DEPENDENCY_ADDED, {"blocked_by": {"from": None, "to": ref}}),
        (ActivityVerb.DEPENDENCY_REMOVED, {"blocked_by": {"from": ref, "to": None}}),
    ]
    assert events[1].actor_id == cast.member.id
    # A dependency is not a change to the task, so nobody editing it is refused.
    assert cast.tasks.get_task(launch.id, actor=cast.owner).version == version


# --- open blocker counts --------------------------------------------------------
def test_open_blocker_counts_ignore_finished_blockers(
    service: TaskDependencyService, cast: Cast
) -> None:
    launch, free = cast.task("Launch"), cast.task("Free")
    block(service, launch, cast.task("Open one"), cast.owner)
    block(service, launch, cast.task("Open two"), cast.owner)
    block(service, launch, cast.task("Finished", status=TaskStatus.DONE), cast.owner)

    counts = cast.tasks.open_blocker_counts([launch, free])

    assert counts == {launch.id: 2, free.id: 0}


# --- ready to start -------------------------------------------------------------
def _unblocked(session: Session) -> list[tuple[uuid.UUID, uuid.UUID, uuid.UUID | None]]:
    """``(recipient, task, actor)`` for every "unblocked" notification."""
    rows = session.scalars(
        select(Notification).where(Notification.kind == NotificationKind.UNBLOCKED)
    ).all()
    return [(row.recipient_id, row.task_id, row.actor_id) for row in rows]


def test_finishing_the_last_open_blocker_tells_the_assignee(
    service: TaskDependencyService, cast: Cast, session: Session
) -> None:
    launch = cast.task("Launch", assignee_id=cast.member.id)
    first, second = cast.task("First"), cast.task("Second")
    block(service, launch, first, cast.owner)
    block(service, launch, second, cast.owner)

    cast.tasks.update_task(first.id, TaskUpdate(status=TaskStatus.DONE), actor=cast.owner)
    assert _unblocked(session) == []  # still waiting on the second

    cast.tasks.update_task(second.id, TaskUpdate(status=TaskStatus.DONE), actor=cast.owner)
    assert _unblocked(session) == [(cast.member.id, launch.id, cast.owner.id)]


def test_nobody_is_told_about_their_own_finish_or_an_unassigned_task(
    service: TaskDependencyService, cast: Cast, session: Session
) -> None:
    mine = cast.task("Mine", assignee_id=cast.member.id)
    nobodys = cast.task("Nobody's")
    blocker = cast.task("Blocker", assignee_id=cast.member.id)
    block(service, mine, blocker, cast.owner)
    block(service, nobodys, blocker, cast.owner)

    cast.tasks.update_task(blocker.id, TaskUpdate(status=TaskStatus.DONE), actor=cast.member)

    assert _unblocked(session) == []


def test_a_finished_waiting_task_is_not_unblocked(
    service: TaskDependencyService, cast: Cast, session: Session
) -> None:
    done_already = cast.task("Done anyway", assignee_id=cast.member.id, status=TaskStatus.DONE)
    blocker = cast.task("Blocker")
    block(service, done_already, blocker, cast.owner)

    cast.tasks.update_task(blocker.id, TaskUpdate(status=TaskStatus.DONE), actor=cast.owner)

    assert _unblocked(session) == []


def test_a_stale_save_unblocks_nobody(
    service: TaskDependencyService, cast: Cast, session: Session
) -> None:
    launch = cast.task("Launch", assignee_id=cast.member.id)
    blocker = cast.task("Blocker")
    block(service, launch, blocker, cast.owner)
    seen = blocker.version
    cast.tasks.update_task(blocker.id, TaskUpdate(title="Renamed"), actor=cast.manager)

    with pytest.raises(TaskConflictError):
        cast.tasks.update_task(
            blocker.id, TaskUpdate(status=TaskStatus.DONE, version=seen), actor=cast.owner
        )

    assert _unblocked(session) == []
