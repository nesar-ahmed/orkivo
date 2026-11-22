"""Unit tests for the activity log (service rules, without HTTP).

The log makes one promise: *every committed change to a task has exactly one
event, and nothing else does*. Each way that could break has a test below ---
a save refused as stale, a race lost at flush, a failure while recording, a
no-op save, bulk changes from a member leaving or a project being deleted --- and
so does the rule that an event, once written, is never changed
(architecture doc section 6.2).
"""

import uuid
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.activity.enums import ActivityVerb
from app.modules.activity.exceptions import ActivityLogIsAppendOnlyError
from app.modules.activity.models import ActivityEvent
from app.modules.activity.recorder import ActivityRecorder
from app.modules.activity.service import ActivityService
from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.projects.schemas import ProjectCreate
from app.modules.projects.service import ProjectService
from app.modules.tasks.enums import TaskStatus
from app.modules.tasks.exceptions import TaskConflictError, TaskNotFoundError
from app.modules.tasks.models import Task
from app.modules.tasks.schemas import TaskCreate, TaskUpdate
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from app.modules.workspaces.exceptions import WorkspaceNotFoundError
from app.modules.workspaces.schemas import InviteCreate, WorkspaceCreate
from app.modules.workspaces.service import WorkspaceService
from tests.synth import PASSWORD, email_for, slug_for

pytestmark = pytest.mark.unit


def _register(accounts: AuthService, label: str, name: str) -> User:
    return accounts.register(
        RegisterRequest(email=email_for(label), password=PASSWORD, display_name=name)
    )


class Cast:
    """A company with an owner and a member, and an outsider."""

    def __init__(self, session: Session) -> None:
        accounts = AuthService(session)
        self.workspaces = WorkspaceService(session)
        self.owner = _register(accounts, "log-owner", "Olive Owner")
        self.member = _register(accounts, "log-member", "Mo Member")
        self.outsider = _register(accounts, "log-outsider", "Oz Outsider")
        self.team = self.workspaces.create_team(
            WorkspaceCreate(name="Log Co", slug=slug_for("log")), actor=self.owner
        )
        invite = self.workspaces.invite(
            self.team.id, InviteCreate(user_id=self.member.id), actor=self.owner
        )
        self.workspaces.accept_invitation(invite.id, actor=self.member)


@pytest.fixture()
def cast(session: Session) -> Cast:
    return Cast(session)


@pytest.fixture()
def tasks(session: Session) -> TaskService:
    return TaskService(session)


@pytest.fixture()
def activity(session: Session) -> ActivityService:
    return ActivityService(session)


def events(session: Session, task_id: uuid.UUID | None = None) -> list[ActivityEvent]:
    """Every event (or one task's), oldest first, straight from the table."""
    stmt = select(ActivityEvent).order_by(ActivityEvent.created_at, ActivityEvent.id)
    if task_id is not None:
        stmt = stmt.where(ActivityEvent.task_id == task_id)
    return list(session.scalars(stmt).all())


def person(user: User) -> dict[str, str]:
    return {"id": str(user.id), "name": user.display_name}


# --- what is recorded --------------------------------------------------------
def test_creating_a_task_records_what_it_started_with(
    tasks: TaskService, cast: Cast, session: Session
) -> None:
    task = tasks.create_task(
        cast.team.id,
        TaskCreate(title="Ship it", assignee_id=cast.member.id),
        actor=cast.owner,
    )

    [created] = events(session, task.id)
    assert created.verb is ActivityVerb.TASK_CREATED
    assert (created.task_title, created.task_version) == ("Ship it", 1)
    assert created.actor_id == cast.owner.id
    assert created.workspace_id == cast.team.id
    # Only what differs from an empty task.
    assert created.changes == {
        "status": {"from": None, "to": "todo"},
        "priority": {"from": None, "to": "medium"},
        "assignee": {"from": None, "to": person(cast.member)},
    }


def test_a_status_move_records_from_and_to_with_the_new_version(
    tasks: TaskService, cast: Cast, session: Session
) -> None:
    task = tasks.create_task(
        cast.team.id, TaskCreate(title="Move me", assignee_id=cast.member.id), actor=cast.owner
    )

    moved = tasks.update_task(
        task.id, TaskUpdate(status=TaskStatus.IN_PROGRESS, version=1), actor=cast.member
    )

    last = events(session, task.id)[-1]
    assert last.verb is ActivityVerb.TASK_UPDATED
    assert last.changes == {"status": {"from": "todo", "to": "in_progress"}}
    assert last.task_version == moved.version == 2
    assert last.actor_id == cast.member.id


def test_one_save_is_one_event_however_many_fields_change(
    tasks: TaskService, cast: Cast, session: Session
) -> None:
    task = tasks.create_task(cast.team.id, TaskCreate(title="Draft"), actor=cast.owner)

    tasks.update_task(
        task.id,
        TaskUpdate(title="Final", status=TaskStatus.DONE, assignee_id=cast.owner.id),
        actor=cast.owner,
    )

    updates = [e for e in events(session, task.id) if e.verb is ActivityVerb.TASK_UPDATED]
    assert len(updates) == 1
    assert updates[0].changes == {
        "title": {"from": "Draft", "to": "Final"},
        "status": {"from": "todo", "to": "done"},
        "assignee": {"from": None, "to": person(cast.owner)},
    }
    # The event names the task as it is after the change.
    assert updates[0].task_title == "Final"


def test_saving_the_values_a_task_already_has_records_nothing(
    tasks: TaskService, cast: Cast, session: Session
) -> None:
    task = tasks.create_task(cast.team.id, TaskCreate(title="Same"), actor=cast.owner)

    tasks.update_task(task.id, TaskUpdate(title="Same", status=TaskStatus.TODO), actor=cast.owner)

    assert [e.verb for e in events(session, task.id)] == [ActivityVerb.TASK_CREATED]


def test_deleting_a_task_keeps_its_name_in_the_feed(
    tasks: TaskService, activity: ActivityService, cast: Cast, session: Session
) -> None:
    task = tasks.create_task(cast.team.id, TaskCreate(title="Doomed"), actor=cast.member)

    tasks.delete_task(task.id, actor=cast.member)

    deleted = events(session, task.id)[-1]
    assert deleted.verb is ActivityVerb.TASK_DELETED
    assert (deleted.task_id, deleted.task_title) == (task.id, "Doomed")
    # The task's own history is gone with the task; the workspace feed keeps it.
    with pytest.raises(TaskNotFoundError):
        activity.task_history(task.id, actor=cast.owner)
    feed, _total, _pages = activity.workspace_feed(cast.team.id, actor=cast.owner)
    assert feed[0].verb is ActivityVerb.TASK_DELETED


# --- what is never recorded --------------------------------------------------
def test_a_save_refused_as_stale_leaves_no_event(
    tasks: TaskService, cast: Cast, session: Session
) -> None:
    task = tasks.create_task(
        cast.team.id, TaskCreate(title="Contested", assignee_id=cast.member.id), actor=cast.owner
    )
    tasks.update_task(task.id, TaskUpdate(title="First"), actor=cast.member)
    before = len(events(session, task.id))

    with pytest.raises(TaskConflictError):
        tasks.update_task(task.id, TaskUpdate(title="Second", version=1), actor=cast.owner)

    assert len(events(session, task.id)) == before


def test_a_race_lost_at_flush_leaves_no_event(
    tasks: TaskService, cast: Cast, session: Session
) -> None:
    """Someone else's save lands between our read and our write."""
    task = tasks.create_task(cast.team.id, TaskCreate(title="Raced"), actor=cast.owner)
    # Behind this session's back: the loaded task keeps its old version.
    session.execute(
        update(Task).where(Task.id == task.id).values(version=Task.version + 1),
        execution_options={"synchronize_session": False},
    )
    session.commit()

    with pytest.raises(TaskConflictError):
        tasks.update_task(task.id, TaskUpdate(title="Too late"), actor=cast.owner)

    assert [e.verb for e in events(session, task.id)] == [ActivityVerb.TASK_CREATED]


def test_a_change_is_never_committed_without_its_event(
    tasks: TaskService, cast: Cast, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If recording fails, the change is rolled back with it."""
    task = tasks.create_task(cast.team.id, TaskCreate(title="Atomic"), actor=cast.owner)

    def broken(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("log unavailable")

    monkeypatch.setattr(ActivityRecorder, "record", broken)
    with pytest.raises(RuntimeError):
        tasks.update_task(task.id, TaskUpdate(status=TaskStatus.DONE), actor=cast.owner)
    monkeypatch.undo()

    session.expire_all()
    fresh = session.get(Task, task.id)
    assert fresh is not None
    assert (fresh.status, fresh.version) == (TaskStatus.TODO, 1)
    assert [e.verb for e in events(session, task.id)] == [ActivityVerb.TASK_CREATED]


# --- conflicts ---------------------------------------------------------------
def test_a_keep_mine_save_records_exactly_what_it_overwrote(
    tasks: TaskService, cast: Cast, session: Session
) -> None:
    """After a 409 the client re-sends its edit on top of the latest version."""
    task = tasks.create_task(
        cast.team.id, TaskCreate(title="Shared", assignee_id=cast.member.id), actor=cast.owner
    )
    theirs = tasks.update_task(task.id, TaskUpdate(title="Theirs", version=1), actor=cast.member)
    with pytest.raises(TaskConflictError):
        tasks.update_task(task.id, TaskUpdate(title="Mine", version=1), actor=cast.owner)

    tasks.update_task(
        task.id, TaskUpdate(title="Mine", version=theirs.version), actor=cast.owner
    )

    last = events(session, task.id)[-1]
    assert last.changes == {"title": {"from": "Theirs", "to": "Mine"}}
    assert last.actor_id == cast.owner.id
    assert last.task_version == 3


# --- bulk changes ------------------------------------------------------------
def test_a_member_leaving_records_each_release(
    tasks: TaskService, cast: Cast, session: Session
) -> None:
    held = [
        tasks.create_task(
            cast.team.id,
            TaskCreate(title=f"Held {n}", assignee_id=cast.member.id),
            actor=cast.owner,
        )
        for n in range(2)
    ]

    cast.workspaces.remove_member(cast.team.id, cast.member.id, actor=cast.owner)

    for task in held:
        last = events(session, task.id)[-1]
        assert last.verb is ActivityVerb.TASK_UPDATED
        assert last.changes == {"assignee": {"from": person(cast.member), "to": None}}
        assert (last.actor_id, last.task_version, last.task_title) == (
            cast.owner.id,
            2,
            task.title,
        )


def test_deleting_a_project_records_each_detach_with_the_old_name(
    tasks: TaskService, cast: Cast, session: Session
) -> None:
    projects = ProjectService(session)
    project = projects.create_project(cast.team.id, ProjectCreate(name="Sunset"), actor=cast.owner)
    task = tasks.create_task(
        cast.team.id, TaskCreate(title="Inside", project_id=project.id), actor=cast.owner
    )

    projects.delete_project(project.id, actor=cast.owner)

    last = events(session, task.id)[-1]
    assert last.changes == {
        "project": {"from": {"id": str(project.id), "name": "Sunset"}, "to": None}
    }


# --- append-only -------------------------------------------------------------
def test_an_event_can_never_be_changed(tasks: TaskService, cast: Cast, session: Session) -> None:
    task = tasks.create_task(cast.team.id, TaskCreate(title="Immutable"), actor=cast.owner)
    [event] = events(session, task.id)

    event.task_title = "Rewritten"
    with pytest.raises(ActivityLogIsAppendOnlyError):
        session.flush()
    session.rollback()


def test_an_event_can_never_be_removed(tasks: TaskService, cast: Cast, session: Session) -> None:
    task = tasks.create_task(cast.team.id, TaskCreate(title="Permanent"), actor=cast.owner)
    [event] = events(session, task.id)

    session.delete(event)
    with pytest.raises(ActivityLogIsAppendOnlyError):
        session.flush()
    session.rollback()
    assert len(events(session, task.id)) == 1


# --- reading -----------------------------------------------------------------
def test_history_is_newest_first_and_paginated(
    tasks: TaskService, activity: ActivityService, cast: Cast
) -> None:
    task = tasks.create_task(cast.team.id, TaskCreate(title="v1"), actor=cast.owner)
    for title in ("v2", "v3"):
        tasks.update_task(task.id, TaskUpdate(title=title), actor=cast.owner)

    page, total, pages = activity.task_history(task.id, actor=cast.member, page_size=2)

    assert (total, pages) == (3, 2)
    assert [e.changes.get("title", {}).get("to") for e in page] == ["v3", "v2"]


def test_outsiders_cannot_read_history_or_the_feed(
    tasks: TaskService, activity: ActivityService, cast: Cast
) -> None:
    task = tasks.create_task(cast.team.id, TaskCreate(title="Private"), actor=cast.owner)

    with pytest.raises(TaskNotFoundError):
        activity.task_history(task.id, actor=cast.outsider)
    with pytest.raises(WorkspaceNotFoundError):
        activity.workspace_feed(cast.team.id, actor=cast.outsider)


def test_the_feed_stays_inside_its_workspace(
    tasks: TaskService, activity: ActivityService, cast: Cast
) -> None:
    tasks.create_task(cast.team.id, TaskCreate(title="Company work"), actor=cast.owner)
    private = tasks.personal_workspace_id(actor=cast.owner)
    tasks.create_task(private, TaskCreate(title="My errand"), actor=cast.owner)

    feed, total, _pages = activity.workspace_feed(cast.team.id, actor=cast.member)

    assert total == 1
    assert feed[0].task_title == "Company work"
