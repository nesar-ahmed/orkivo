"""Unit tests for who may change or delete one task (``tasks.permissions``).

A company's tasks are read by everyone in it, but changed by fewer people:
owners, admins and managers change or delete any task; a member changes the
tasks they created or hold and deletes the ones they created; a viewer changes
nothing. Each refusal has its own answer --- the policy's 403 for a role or a
suspended company, ``TaskForbiddenError`` for a member reaching for someone
else's task, not found for an outsider --- and what a caller may do to a task is
reported by the same function that refuses them (architecture doc section 9).

Accounts join companies the way the product does --- invite, then accept --- so
no test relies on a membership state a real caller could not reach.
"""

import pytest
from sqlalchemy.orm import Session

from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.tasks.enums import TaskAction, TaskStatus
from app.modules.tasks.exceptions import TaskForbiddenError, TaskNotFoundError
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

EDIT, DELETE = TaskAction.EDIT, TaskAction.DELETE


def _register(accounts: AuthService, label: str) -> User:
    return accounts.register(RegisterRequest(email=email_for(label), password=PASSWORD))


class Cast:
    """A company with one person in each role, plus an outsider."""

    def __init__(self, session: Session) -> None:
        accounts = AuthService(session)
        self.workspaces = WorkspaceService(session)
        self.owner = _register(accounts, "perm-owner")
        self.admin = _register(accounts, "perm-admin")
        self.manager = _register(accounts, "perm-manager")
        self.member = _register(accounts, "perm-member")
        self.colleague = _register(accounts, "perm-colleague")
        self.viewer = _register(accounts, "perm-viewer")
        self.outsider = _register(accounts, "perm-outsider")
        self.team = self.workspaces.create_team(
            WorkspaceCreate(name="Permission Co", slug=slug_for("permissions")), actor=self.owner
        )
        for account, role in (
            (self.admin, WorkspaceRole.ADMIN),
            (self.manager, WorkspaceRole.MANAGER),
            (self.member, WorkspaceRole.MEMBER),
            (self.colleague, WorkspaceRole.MEMBER),
            (self.viewer, WorkspaceRole.VIEWER),
        ):
            invite = self.workspaces.invite(
                self.team.id, InviteCreate(user_id=account.id, role=role), actor=self.owner
            )
            self.workspaces.accept_invitation(invite.id, actor=account)


@pytest.fixture()
def cast(session: Session) -> Cast:
    return Cast(session)


@pytest.fixture()
def tasks(session: Session) -> TaskService:
    return TaskService(session)


def _task(tasks: TaskService, cast: Cast, *, by: User, holder: User | None = None) -> Task:
    return tasks.create_task(
        cast.team.id,
        TaskCreate(title="Shared work", assignee_id=holder.id if holder else None),
        actor=by,
    )


# --- creating ----------------------------------------------------------------
@pytest.mark.parametrize("role", ["owner", "admin", "manager", "member"])
def test_everyone_but_a_viewer_adds_tasks(tasks: TaskService, cast: Cast, role: str) -> None:
    task = _task(tasks, cast, by=getattr(cast, role))

    assert task.owner_id == getattr(cast, role).id


def test_a_viewer_reads_tasks_but_adds_none(tasks: TaskService, cast: Cast) -> None:
    task = _task(tasks, cast, by=cast.owner)

    assert tasks.get_task(task.id, actor=cast.viewer).title == "Shared work"
    with pytest.raises(WorkspaceRoleNotAllowedError):
        _task(tasks, cast, by=cast.viewer)


# --- changing and deleting someone else's task ---------------------------------
@pytest.mark.parametrize("role", ["owner", "admin", "manager"])
def test_people_running_the_work_change_and_delete_any_task(
    tasks: TaskService, cast: Cast, role: str
) -> None:
    actor = getattr(cast, role)
    task = _task(tasks, cast, by=cast.colleague, holder=cast.colleague)

    changed = tasks.update_task(task.id, TaskUpdate(status=TaskStatus.DONE), actor=actor)
    assert changed.status is TaskStatus.DONE

    tasks.delete_task(task.id, actor=actor)
    with pytest.raises(TaskNotFoundError):
        tasks.get_task(task.id, actor=cast.owner)


def test_a_member_may_not_change_or_delete_someone_elses_task(
    tasks: TaskService, cast: Cast
) -> None:
    task = _task(tasks, cast, by=cast.colleague)

    with pytest.raises(TaskForbiddenError) as refused:
        tasks.update_task(task.id, TaskUpdate(title="Hijacked"), actor=cast.member)
    assert refused.value.code == "TASK_FORBIDDEN"
    with pytest.raises(TaskForbiddenError):
        tasks.delete_task(task.id, actor=cast.member)

    unchanged = tasks.get_task(task.id, actor=cast.member)
    assert (unchanged.title, unchanged.version) == ("Shared work", 1)


def test_a_member_changes_and_deletes_a_task_they_created(tasks: TaskService, cast: Cast) -> None:
    task = _task(tasks, cast, by=cast.member, holder=cast.colleague)

    changed = tasks.update_task(task.id, TaskUpdate(title="Mine, renamed"), actor=cast.member)
    assert changed.title == "Mine, renamed"

    tasks.delete_task(task.id, actor=cast.member)
    with pytest.raises(TaskNotFoundError):
        tasks.get_task(task.id, actor=cast.member)


def test_a_member_changes_but_may_not_delete_a_task_they_hold(
    tasks: TaskService, cast: Cast
) -> None:
    task = _task(tasks, cast, by=cast.owner, holder=cast.member)

    moved = tasks.update_task(task.id, TaskUpdate(status=TaskStatus.IN_PROGRESS), actor=cast.member)
    assert moved.status is TaskStatus.IN_PROGRESS

    with pytest.raises(TaskForbiddenError):
        tasks.delete_task(task.id, actor=cast.member)


def test_handing_a_task_on_hands_on_the_right_to_change_it(tasks: TaskService, cast: Cast) -> None:
    """The holder decided before the change is the one checked, and the next save
    is checked against the new holder."""
    task = _task(tasks, cast, by=cast.owner, holder=cast.member)

    tasks.update_task(task.id, TaskUpdate(assignee_id=cast.colleague.id), actor=cast.member)

    with pytest.raises(TaskForbiddenError):
        tasks.update_task(task.id, TaskUpdate(title="Too late"), actor=cast.member)
    assert tasks.update_task(task.id, TaskUpdate(title="Mine now"), actor=cast.colleague).title


def test_a_viewer_is_refused_by_role_before_any_task_rule(tasks: TaskService, cast: Cast) -> None:
    task = _task(tasks, cast, by=cast.owner, holder=cast.viewer)

    for attempt in (
        lambda: tasks.update_task(task.id, TaskUpdate(title="Nope"), actor=cast.viewer),
        lambda: tasks.delete_task(task.id, actor=cast.viewer),
    ):
        with pytest.raises(WorkspaceRoleNotAllowedError):
            attempt()


def test_an_outsider_still_reads_every_task_as_missing(tasks: TaskService, cast: Cast) -> None:
    task = _task(tasks, cast, by=cast.owner)

    for attempt in (
        lambda: tasks.get_task(task.id, actor=cast.outsider),
        lambda: tasks.update_task(task.id, TaskUpdate(title="Mine"), actor=cast.outsider),
        lambda: tasks.delete_task(task.id, actor=cast.outsider),
    ):
        with pytest.raises(TaskNotFoundError):
            attempt()


def test_a_suspended_company_refuses_even_a_members_own_task(
    tasks: TaskService, cast: Cast
) -> None:
    """Suspension is answered before the task's own rule, for every role."""
    own = _task(tasks, cast, by=cast.member)
    cast.workspaces.set_suspended(cast.team.id, suspended=True, note=None)

    for actor in (cast.member, cast.manager, cast.owner):
        with pytest.raises(WorkspaceSuspendedError):
            tasks.update_task(own.id, TaskUpdate(title="Thaw"), actor=actor)


def test_the_permission_check_comes_before_the_version_check(
    tasks: TaskService, cast: Cast
) -> None:
    """A stale version must not tell a member more than "not yours"."""
    task = _task(tasks, cast, by=cast.colleague)

    with pytest.raises(TaskForbiddenError):
        tasks.update_task(task.id, TaskUpdate(title="x", version=99), actor=cast.member)


# --- what the caller is told they may do ----------------------------------------
def test_capabilities_follow_the_same_rule_as_the_refusals(tasks: TaskService, cast: Cast) -> None:
    created = _task(tasks, cast, by=cast.member)
    held = _task(tasks, cast, by=cast.owner, holder=cast.member)
    others = _task(tasks, cast, by=cast.colleague)
    page = [created, held, others]

    def seen_by(actor: User) -> list[list[TaskAction]]:
        found = tasks.task_capabilities(page, actor=actor)
        return [found[task.id] for task in page]

    assert seen_by(cast.member) == [[EDIT, DELETE], [EDIT], []]
    assert seen_by(cast.manager) == [[EDIT, DELETE]] * 3
    assert seen_by(cast.viewer) == [[], [], []]
    assert seen_by(cast.outsider) == [[], [], []]

    cast.workspaces.set_suspended(cast.team.id, suspended=True, note=None)
    assert seen_by(cast.owner) == [[], [], []]


def test_every_task_in_a_private_workspace_is_its_owners(tasks: TaskService, cast: Cast) -> None:
    private = tasks.personal_workspace_id(actor=cast.viewer)
    task = tasks.create_task(private, TaskCreate(title="Errand"), actor=cast.viewer)

    assert tasks.task_capabilities([task], actor=cast.viewer)[task.id] == [EDIT, DELETE]
