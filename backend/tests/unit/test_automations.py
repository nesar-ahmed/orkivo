"""Unit tests for workspace automation rules (service rules, without HTTP).

A company switches catalogue rules on and off; a rule runs inside the save that
triggers it. The tests pin who may switch what, who each rule tells --- once each,
never the person who acted, only current members --- and that only a real move to
Done sets a rule off (architecture doc sections 5, 6.2 and 9).

Accounts join companies the way the product does --- invite, then accept --- so
no test relies on a membership state a real caller could not reach.
"""

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.activity.enums import ActivityVerb
from app.modules.activity.models import ActivityEvent
from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.automations.enums import (
    AutomationRecipient,
    AutomationRule,
    AutomationTrigger,
)
from app.modules.automations.service import AutomationService
from app.modules.notifications.enums import NotificationKind
from app.modules.notifications.models import Notification
from app.modules.notifications.service import NotificationService
from app.modules.tasks.enums import TaskStatus
from app.modules.tasks.exceptions import TaskConflictError
from app.modules.tasks.models import Task
from app.modules.tasks.schemas import (
    BulkTaskChanges,
    BulkTaskRef,
    BulkTaskUpdate,
    TaskCreate,
    TaskUpdate,
)
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from app.modules.workspaces.enums import WorkspaceRole
from app.modules.workspaces.exceptions import (
    PersonalWorkspaceError,
    WorkspaceNotFoundError,
    WorkspaceRoleNotAllowedError,
    WorkspaceSuspendedError,
)
from app.modules.workspaces.schemas import InviteCreate, WorkspaceCreate
from app.modules.workspaces.service import WorkspaceService
from tests.synth import PASSWORD, email_for, slug_for

pytestmark = pytest.mark.unit

CREATOR = AutomationRule.NOTIFY_CREATOR_ON_DONE
WATCHERS = AutomationRule.NOTIFY_WATCHERS_ON_DONE
OWNERS = AutomationRule.NOTIFY_OWNERS_ON_DONE


def _register(accounts: AuthService, label: str, name: str) -> User:
    return accounts.register(
        RegisterRequest(email=email_for(label), password=PASSWORD, display_name=name)
    )


class Cast:
    """A company with one person in each role, a second member, and an outsider."""

    def __init__(self, session: Session) -> None:
        accounts = AuthService(session)
        self.session = session
        self.workspaces = WorkspaceService(session)
        self.tasks = TaskService(session)
        self.automations = AutomationService(session)
        self.owner = _register(accounts, "auto-owner", "Olive Owner")
        self.admin = _register(accounts, "auto-admin", "Ada Admin")
        self.manager = _register(accounts, "auto-manager", "Max Manager")
        self.member = _register(accounts, "auto-member", "Mo Member")
        self.colleague = _register(accounts, "auto-colleague", "Cy Colleague")
        self.viewer = _register(accounts, "auto-viewer", "Vi Viewer")
        self.outsider = _register(accounts, "auto-outsider", "Oz Outsider")
        self.team = self.workspaces.create_team(
            WorkspaceCreate(name="Auto Co", slug=slug_for("auto")), actor=self.owner
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

    def switch_on(self, *rules: AutomationRule) -> None:
        for rule in rules:
            self.automations.set_enabled(self.team.id, rule, enabled=True, actor=self.manager)

    def task(self, title: str, *, by: User, **fields: Any) -> Task:
        return self.tasks.create_task(
            self.team.id, TaskCreate.model_validate({"title": title, **fields}), actor=by
        )

    def finish(self, task: Task, *, by: User) -> Task:
        return self.tasks.update_task(task.id, TaskUpdate(status=TaskStatus.DONE), actor=by)


@pytest.fixture()
def cast(session: Session) -> Cast:
    return Cast(session)


def completed(session: Session, person: User) -> list[tuple[str, str | None]]:
    """The "completed" notifications ``person`` received: (task title, actor name)."""
    rows = session.scalars(
        select(Notification)
        .where(
            Notification.recipient_id == person.id,
            Notification.kind == NotificationKind.COMPLETED,
        )
        .order_by(Notification.created_at, Notification.id)
    ).all()
    return [(row.task.title, row.actor.display_name if row.actor else None) for row in rows]


# --- the settings --------------------------------------------------------------------
def test_every_rule_is_off_until_someone_switches_it(cast: Cast) -> None:
    rules = cast.automations.list_rules(cast.team.id, actor=cast.viewer)

    assert [state.rule for state in rules] == [CREATOR, WATCHERS, OWNERS]
    assert [(state.enabled, state.updated_by) for state in rules] == [(False, None)] * 3
    assert {(state.spec.trigger, state.spec.recipient) for state in rules} == {
        (AutomationTrigger.TASK_COMPLETED, AutomationRecipient.TASK_CREATOR),
        (AutomationTrigger.TASK_COMPLETED, AutomationRecipient.TASK_WATCHERS),
        (AutomationTrigger.TASK_COMPLETED, AutomationRecipient.WORKSPACE_OWNERS),
    }


@pytest.mark.parametrize("role", ["owner", "admin", "manager"])
def test_people_running_the_work_switch_rules(cast: Cast, role: str) -> None:
    actor = getattr(cast, role)

    state = cast.automations.set_enabled(cast.team.id, CREATOR, enabled=True, actor=actor)

    assert (state.enabled, state.updated_by.id if state.updated_by else None) == (True, actor.id)
    assert cast.automations.list_rules(cast.team.id, actor=cast.member)[0].enabled is True


@pytest.mark.parametrize("role", ["member", "viewer"])
def test_members_and_viewers_see_rules_but_cannot_switch_them(cast: Cast, role: str) -> None:
    with pytest.raises(WorkspaceRoleNotAllowedError):
        cast.automations.set_enabled(cast.team.id, CREATOR, enabled=True, actor=getattr(cast, role))

    assert cast.automations.list_rules(cast.team.id, actor=getattr(cast, role))[0].enabled is False


def test_outsiders_private_workspaces_and_suspended_companies(cast: Cast) -> None:
    with pytest.raises(WorkspaceNotFoundError):
        cast.automations.list_rules(cast.team.id, actor=cast.outsider)

    private = cast.tasks.personal_workspace_id(actor=cast.member)
    with pytest.raises(PersonalWorkspaceError):
        cast.automations.set_enabled(private, CREATOR, enabled=True, actor=cast.member)

    cast.workspaces.set_suspended(cast.team.id, suspended=True, note=None)
    assert len(cast.automations.list_rules(cast.team.id, actor=cast.owner)) == 3
    with pytest.raises(WorkspaceSuspendedError):
        cast.automations.set_enabled(cast.team.id, CREATOR, enabled=True, actor=cast.owner)


def test_switching_to_the_same_state_changes_nothing(cast: Cast) -> None:
    cast.automations.set_enabled(cast.team.id, CREATOR, enabled=True, actor=cast.manager)

    again = cast.automations.set_enabled(cast.team.id, CREATOR, enabled=True, actor=cast.owner)
    off = cast.automations.set_enabled(cast.team.id, CREATOR, enabled=False, actor=cast.admin)

    assert again.updated_by is not None and again.updated_by.id == cast.manager.id
    assert (off.enabled, off.updated_by.id if off.updated_by else None) == (False, cast.admin.id)


# --- running the rules ------------------------------------------------------------------
def test_moving_a_task_to_done_tells_its_creator(cast: Cast, session: Session) -> None:
    cast.switch_on(CREATOR)
    task = cast.task("Ship it", by=cast.manager, assignee_id=cast.member.id)

    cast.finish(task, by=cast.member)

    assert completed(session, cast.manager) == [("Ship it", "Mo Member")]
    assert completed(session, cast.member) == []  # never the person who finished it


def automation_events(session: Session, task: Task) -> list[ActivityEvent]:
    return list(
        session.scalars(
            select(ActivityEvent).where(
                ActivityEvent.task_id == task.id,
                ActivityEvent.verb == ActivityVerb.AUTOMATION_NOTIFIED,
            )
        )
    )


def test_the_tasks_history_says_who_an_automation_told_and_why(
    cast: Cast, session: Session
) -> None:
    cast.switch_on(CREATOR, OWNERS)
    task = cast.task("Audited", by=cast.manager, assignee_id=cast.member.id)

    cast.finish(task, by=cast.member)

    (event,) = automation_events(session, task)
    assert event.actor_id == cast.member.id  # it ran because of their change
    assert event.task_version == 2
    assert event.changes == {
        "notified": {
            "from": None,
            "to": [
                {"id": str(cast.manager.id), "name": "Max Manager"},
                {"id": str(cast.owner.id), "name": "Olive Owner"},
            ],
        },
        "rules": {"from": None, "to": ["notify_creator_on_done", "notify_owners_on_done"]},
    }


def test_finishing_your_own_task_tells_nobody(cast: Cast, session: Session) -> None:
    cast.switch_on(CREATOR, OWNERS)
    task = cast.task("Mine", by=cast.owner)

    cast.finish(task, by=cast.owner)

    assert completed(session, cast.owner) == []
    # Nobody was told, so the history has nothing to say either.
    assert automation_events(session, task) == []


def test_watchers_hear_when_the_watchers_rule_is_on(cast: Cast, session: Session) -> None:
    cast.switch_on(WATCHERS)
    task = cast.task("Watched", by=cast.manager, assignee_id=cast.member.id)
    NotificationService(session).watch(task.id, actor=cast.colleague)

    cast.finish(task, by=cast.member)

    # The creator watches what they create; the colleague chose to.
    assert completed(session, cast.colleague) == [("Watched", "Mo Member")]
    assert completed(session, cast.manager) == [("Watched", "Mo Member")]
    assert completed(session, cast.admin) == []


def test_owners_hear_about_every_finished_task_without_watching_it(
    cast: Cast, session: Session
) -> None:
    cast.switch_on(OWNERS)
    task = cast.task("Someone's", by=cast.member)

    cast.finish(task, by=cast.member)

    assert completed(session, cast.owner) == [("Someone's", "Mo Member")]
    assert cast.owner.id not in {
        person.id for person in NotificationService(session).watchers(task.id, actor=cast.owner)[0]
    }


def test_someone_several_rules_name_is_told_once(cast: Cast, session: Session) -> None:
    cast.switch_on(CREATOR, WATCHERS, OWNERS)
    # The owner is its creator, a watcher and an owner at once.
    task = cast.task("Everything on", by=cast.owner, assignee_id=cast.member.id)

    cast.finish(task, by=cast.member)

    assert completed(session, cast.owner) == [("Everything on", "Mo Member")]


def test_only_a_move_to_done_sets_a_rule_off(cast: Cast, session: Session) -> None:
    cast.switch_on(CREATOR)
    started = cast.task("Started", by=cast.manager)
    cast.tasks.update_task(started.id, TaskUpdate(status=TaskStatus.IN_PROGRESS), actor=cast.owner)
    cast.task("Born done", by=cast.owner, status=TaskStatus.DONE)
    finished = cast.finish(started, by=cast.owner)
    cast.tasks.update_task(finished.id, TaskUpdate(title="Renamed while done"), actor=cast.owner)

    # Once, for the one real move; notifications name the task by its current title.
    assert completed(session, cast.manager) == [("Renamed while done", "Olive Owner")]


def test_a_rule_that_is_off_tells_nobody(cast: Cast, session: Session) -> None:
    cast.switch_on(CREATOR)
    cast.automations.set_enabled(cast.team.id, CREATOR, enabled=False, actor=cast.owner)
    task = cast.task("Quiet", by=cast.manager, assignee_id=cast.member.id)

    cast.finish(task, by=cast.member)

    assert completed(session, cast.manager) == []


def test_a_save_refused_as_stale_runs_no_rule(cast: Cast, session: Session) -> None:
    cast.switch_on(CREATOR)
    task = cast.task("Contested", by=cast.manager)
    cast.tasks.update_task(task.id, TaskUpdate(title="Changed first"), actor=cast.owner)

    with pytest.raises(TaskConflictError):
        cast.tasks.update_task(
            task.id, TaskUpdate(status=TaskStatus.DONE, version=1), actor=cast.owner
        )

    assert completed(session, cast.manager) == []


def test_a_bulk_move_to_done_tells_the_creator_once_per_task(cast: Cast, session: Session) -> None:
    cast.switch_on(CREATOR)
    first, second = cast.task("First", by=cast.manager), cast.task("Second", by=cast.manager)

    cast.tasks.bulk_update(
        cast.team.id,
        BulkTaskUpdate(
            tasks=[BulkTaskRef(id=first.id), BulkTaskRef(id=second.id)],
            changes=BulkTaskChanges(status=TaskStatus.DONE),
        ),
        actor=cast.owner,
    )

    assert sorted(completed(session, cast.manager)) == [
        ("First", "Olive Owner"),
        ("Second", "Olive Owner"),
    ]


def test_rules_belong_to_their_workspace(cast: Cast, session: Session) -> None:
    cast.switch_on(CREATOR)
    other = cast.workspaces.create_team(
        WorkspaceCreate(name="Other Co", slug=slug_for("auto-other")), actor=cast.owner
    )
    invite = cast.workspaces.invite(
        other.id, InviteCreate(user_id=cast.member.id, role=WorkspaceRole.MEMBER), actor=cast.owner
    )
    cast.workspaces.accept_invitation(invite.id, actor=cast.member)
    task = cast.tasks.create_task(
        other.id, TaskCreate(title="Elsewhere", assignee_id=cast.member.id), actor=cast.owner
    )

    cast.tasks.update_task(task.id, TaskUpdate(status=TaskStatus.DONE), actor=cast.owner)
    cast.tasks.update_task(task.id, TaskUpdate(status=TaskStatus.TODO), actor=cast.member)
    cast.tasks.update_task(task.id, TaskUpdate(status=TaskStatus.DONE), actor=cast.member)

    assert completed(session, cast.owner) == []
