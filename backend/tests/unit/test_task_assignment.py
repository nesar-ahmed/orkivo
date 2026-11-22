"""Unit tests for task assignment (service rules, without HTTP).

An assignee is a *member of the task's workspace*, or nobody. That one sentence
has three ways to break, and each has tests below: assigning someone from outside
the tenant, filtering by assignee, and a member leaving while still holding work
(architecture doc sections 6 and 9).

Accounts join companies the way the product does --- invite, then accept --- so
no test relies on a membership state a real caller could not reach.
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.tasks.enums import AssigneeScope
from app.modules.tasks.exceptions import AssigneeNotMemberError, TaskConflictError
from app.modules.tasks.models import Task
from app.modules.tasks.schemas import TaskCreate, TaskUpdate
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from app.modules.workspaces.access import WorkspaceAccessPolicy
from app.modules.workspaces.schemas import InviteCreate, WorkspaceCreate
from app.modules.workspaces.service import WorkspaceService
from tests.synth import PASSWORD, email_for, slug_for

pytestmark = pytest.mark.unit


def _register(accounts: AuthService, label: str) -> User:
    return accounts.register(RegisterRequest(email=email_for(label), password=PASSWORD))


class Cast:
    """A company with an owner and a member, plus an outsider with a company of their own."""

    def __init__(self, session: Session) -> None:
        accounts = AuthService(session)
        self.workspaces = WorkspaceService(session)
        self.owner = _register(accounts, "assign-owner")
        self.member = _register(accounts, "assign-member")
        self.outsider = _register(accounts, "assign-outsider")

        self.team = self.workspaces.create_team(
            WorkspaceCreate(name="Assign Co", slug=slug_for("assign")), actor=self.owner
        )
        invite = self.workspaces.invite(
            self.team.id, InviteCreate(email=self.member.email), actor=self.owner
        )
        self.workspaces.accept_invitation(invite.id, actor=self.member)

        self.elsewhere = self.workspaces.create_team(
            WorkspaceCreate(name="Elsewhere Co", slug=slug_for("elsewhere")), actor=self.outsider
        )
        tasks = TaskService(session)
        self.owner_private = tasks.personal_workspace_id(actor=self.owner)


@pytest.fixture()
def cast(session: Session) -> Cast:
    return Cast(session)


@pytest.fixture()
def service(session: Session) -> TaskService:
    return TaskService(session)


# --- assigning -------------------------------------------------------------
def test_new_tasks_are_unassigned_by_default(service: TaskService, cast: Cast) -> None:
    task = service.create_task(cast.team.id, TaskCreate(title="Nobody yet"), actor=cast.owner)

    assert task.assignee_id is None
    assert task.assignee is None


def test_a_task_can_be_created_for_a_colleague(service: TaskService, cast: Cast) -> None:
    task = service.create_task(
        cast.team.id,
        TaskCreate(title="Yours", assignee_id=cast.member.id),
        actor=cast.owner,
    )

    assert task.assignee_id == cast.member.id
    assert task.assignee is not None
    assert task.assignee.display_name == cast.member.display_name


def test_an_outsider_cannot_be_assigned_and_nothing_is_created(
    service: TaskService, cast: Cast, session: Session
) -> None:
    with pytest.raises(AssigneeNotMemberError):
        service.create_task(
            cast.team.id,
            TaskCreate(title="Leaky", assignee_id=cast.outsider.id),
            actor=cast.owner,
        )

    assert session.query(Task).filter_by(workspace_id=cast.team.id).count() == 0


def test_an_unknown_account_reads_exactly_like_an_outsider(
    service: TaskService, cast: Cast
) -> None:
    """Same error for "no such account" and "not in this tenant": no oracle."""
    with pytest.raises(AssigneeNotMemberError) as unknown:
        service.create_task(
            cast.team.id, TaskCreate(title="Ghost", assignee_id=uuid.uuid4()), actor=cast.owner
        )
    with pytest.raises(AssigneeNotMemberError) as outsider:
        service.create_task(
            cast.team.id,
            TaskCreate(title="Ghost", assignee_id=cast.outsider.id),
            actor=cast.owner,
        )

    assert unknown.value.code == outsider.value.code
    assert unknown.value.message == outsider.value.message


def test_a_private_task_can_only_be_assigned_to_its_owner(
    service: TaskService, cast: Cast
) -> None:
    mine = service.create_task(
        cast.owner_private, TaskCreate(title="Mine", assignee_id=cast.owner.id), actor=cast.owner
    )
    assert mine.assignee_id == cast.owner.id

    # A colleague from a shared company is still not in the private workspace.
    with pytest.raises(AssigneeNotMemberError):
        service.update_task(mine.id, TaskUpdate(assignee_id=cast.member.id), actor=cast.owner)


def test_reassigning_returns_the_new_person_immediately(service: TaskService, cast: Cast) -> None:
    """The response must not show the previous assignee from the loaded relationship."""
    task = service.create_task(
        cast.team.id, TaskCreate(title="Pass it on", assignee_id=cast.owner.id), actor=cast.owner
    )

    updated = service.update_task(task.id, TaskUpdate(assignee_id=cast.member.id), actor=cast.owner)

    assert updated.assignee_id == cast.member.id
    assert updated.assignee is not None
    assert updated.assignee.id == cast.member.id
    assert updated.version == task.version
    assert updated.updated_by is not None and updated.updated_by.id == cast.owner.id


def test_null_clears_the_assignee_and_omitting_it_keeps_it(
    service: TaskService, cast: Cast
) -> None:
    task = service.create_task(
        cast.team.id, TaskCreate(title="Held", assignee_id=cast.member.id), actor=cast.owner
    )

    kept = service.update_task(task.id, TaskUpdate(title="Held, renamed"), actor=cast.owner)
    assert kept.assignee_id == cast.member.id

    cleared = service.update_task(task.id, TaskUpdate(assignee_id=None), actor=cast.owner)
    assert cleared.assignee_id is None
    assert cleared.assignee is None


def test_assigning_with_a_stale_version_is_a_conflict(service: TaskService, cast: Cast) -> None:
    task = service.create_task(cast.team.id, TaskCreate(title="Contested"), actor=cast.member)
    seen = task.version
    service.update_task(task.id, TaskUpdate(title="Changed first"), actor=cast.member)

    with pytest.raises(TaskConflictError):
        service.update_task(
            task.id, TaskUpdate(assignee_id=cast.member.id, version=seen), actor=cast.owner
        )

    assert service.get_task(task.id, actor=cast.owner).assignee_id is None


def test_membership_lookup_answers_only_for_members(cast: Cast, session: Session) -> None:
    policy = WorkspaceAccessPolicy(session)

    found = policy.members_among(
        cast.team.id, {cast.owner.id, cast.member.id, cast.outsider.id, uuid.uuid4()}
    )

    assert set(found) == {cast.owner.id, cast.member.id}
    assert policy.members_among(cast.team.id, set()) == {}


# --- filtering -------------------------------------------------------------
@pytest.fixture()
def spread(service: TaskService, cast: Cast) -> dict[str, Task]:
    """One task for each person and one for nobody, oldest first."""
    return {
        "owner": service.create_task(
            cast.team.id, TaskCreate(title="Owner's", assignee_id=cast.owner.id), actor=cast.owner
        ),
        "member": service.create_task(
            cast.team.id,
            TaskCreate(title="Member's", assignee_id=cast.member.id),
            actor=cast.owner,
        ),
        "nobody": service.create_task(cast.team.id, TaskCreate(title="Nobody's"), actor=cast.owner),
    }


def test_filter_by_a_members_id(service: TaskService, cast: Cast, spread: dict[str, Task]) -> None:
    items, total = service.list_tasks(cast.team.id, actor=cast.owner, assignee=cast.member.id)

    assert total == 1
    assert [task.title for task in items] == ["Member's"]


def test_me_means_the_caller(service: TaskService, cast: Cast, spread: dict[str, Task]) -> None:
    as_owner, _ = service.list_tasks(cast.team.id, actor=cast.owner, assignee=AssigneeScope.ME)
    as_member, _ = service.list_tasks(cast.team.id, actor=cast.member, assignee=AssigneeScope.ME)

    assert [task.title for task in as_owner] == ["Owner's"]
    assert [task.title for task in as_member] == ["Member's"]


def test_none_means_unassigned(service: TaskService, cast: Cast, spread: dict[str, Task]) -> None:
    items, total = service.list_tasks(cast.team.id, actor=cast.owner, assignee=AssigneeScope.NONE)

    assert total == 1
    assert [task.title for task in items] == ["Nobody's"]


def test_filtering_by_an_outsider_finds_nothing(
    service: TaskService, cast: Cast, spread: dict[str, Task]
) -> None:
    items, total = service.list_tasks(cast.team.id, actor=cast.owner, assignee=cast.outsider.id)

    assert total == 0
    assert list(items) == []


# --- leaving ---------------------------------------------------------------
def test_removing_a_member_releases_their_tasks_in_that_company_only(
    service: TaskService, cast: Cast, session: Session
) -> None:
    held = service.create_task(
        cast.team.id, TaskCreate(title="In the team", assignee_id=cast.member.id), actor=cast.owner
    )
    other = service.create_task(
        cast.team.id, TaskCreate(title="Owner keeps", assignee_id=cast.owner.id), actor=cast.owner
    )
    private = service.create_task(
        service.personal_workspace_id(actor=cast.member),
        TaskCreate(title="Member's own", assignee_id=cast.member.id),
        actor=cast.member,
    )
    before = held.version

    cast.workspaces.remove_member(cast.team.id, cast.member.id, actor=cast.owner)

    released = session.get(Task, held.id)
    assert released is not None
    assert released.assignee_id is None
    assert released.assignee is None
    # Recorded like any other save: a new version, by whoever removed them.
    assert released.version == before + 1
    assert released.updated_by_id == cast.owner.id
    # Nobody else's assignment, and nothing in another tenant, is touched.
    assert service.get_task(other.id, actor=cast.owner).assignee_id == cast.owner.id
    assert service.get_task(private.id, actor=cast.member).assignee_id == cast.member.id


def test_leaving_voluntarily_releases_the_leavers_tasks(
    service: TaskService, cast: Cast
) -> None:
    task = service.create_task(
        cast.team.id, TaskCreate(title="Dropped", assignee_id=cast.member.id), actor=cast.owner
    )

    cast.workspaces.remove_member(cast.team.id, cast.member.id, actor=cast.member)

    released = service.get_task(task.id, actor=cast.owner)
    assert released.assignee_id is None
    assert released.updated_by_id == cast.member.id


def test_an_editor_holding_the_old_version_gets_a_conflict_after_release(
    service: TaskService, cast: Cast
) -> None:
    """A stale save must not silently re-assign someone who has left."""
    task = service.create_task(
        cast.team.id,
        TaskCreate(title="Open in a tab", assignee_id=cast.member.id),
        actor=cast.owner,
    )
    seen = task.version

    cast.workspaces.remove_member(cast.team.id, cast.member.id, actor=cast.owner)

    with pytest.raises(TaskConflictError):
        service.update_task(task.id, TaskUpdate(title="Stale", version=seen), actor=cast.owner)


def test_a_departed_member_cannot_be_assigned_again(service: TaskService, cast: Cast) -> None:
    task = service.create_task(cast.team.id, TaskCreate(title="Later"), actor=cast.owner)
    cast.workspaces.remove_member(cast.team.id, cast.member.id, actor=cast.owner)

    with pytest.raises(AssigneeNotMemberError):
        service.update_task(task.id, TaskUpdate(assignee_id=cast.member.id), actor=cast.owner)
