"""Unit tests for watchers and notifications (service rules, without HTTP).

Who hears about what is a short list of rules --- watching, assigned, commented,
mentioned, never yourself, never outside the workspace --- and each has tests
below. So do the guarantees around them: a refused change tells nobody, leaving a
company empties your inbox of it, and an inbox is private
(architecture doc sections 6.2 and 9).
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.comments.schemas import CommentCreate, CommentUpdate
from app.modules.comments.service import CommentService
from app.modules.notifications.enums import NotificationKind
from app.modules.notifications.exceptions import NotificationNotFoundError
from app.modules.notifications.models import Notification, TaskWatcher
from app.modules.notifications.service import NotificationService
from app.modules.tasks.exceptions import TaskConflictError, TaskNotFoundError
from app.modules.tasks.models import Task
from app.modules.tasks.schemas import TaskCreate, TaskUpdate
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from app.modules.workspaces import repository as workspace_repository
from app.modules.workspaces.schemas import InviteCreate, WorkspaceCreate
from app.modules.workspaces.service import WorkspaceService
from tests.synth import PASSWORD, email_for, slug_for

pytestmark = pytest.mark.unit


def _register(accounts: AuthService, label: str, name: str) -> User:
    return accounts.register(
        RegisterRequest(email=email_for(label), password=PASSWORD, display_name=name)
    )


class Cast:
    """A company with Olive (owner), Mo and Pat (members), and Oz outside it."""

    def __init__(self, session: Session) -> None:
        accounts = AuthService(session)
        self.workspaces = WorkspaceService(session)
        self.olive = _register(accounts, "bell-olive", "Olive Owner")
        self.mo = _register(accounts, "bell-mo", "Mo Member")
        self.pat = _register(accounts, "bell-pat", "Pat Peer")
        self.oz = _register(accounts, "bell-oz", "Oz Outsider")
        self.team = self.workspaces.create_team(
            WorkspaceCreate(name="Bell Co", slug=slug_for("bell")), actor=self.olive
        )
        for account in (self.mo, self.pat):
            invite = self.workspaces.invite(
                self.team.id, InviteCreate(user_id=account.id), actor=self.olive
            )
            self.workspaces.accept_invitation(invite.id, actor=account)


@pytest.fixture()
def cast(session: Session) -> Cast:
    return Cast(session)


@pytest.fixture()
def tasks(session: Session) -> TaskService:
    return TaskService(session)


@pytest.fixture()
def comments(session: Session) -> CommentService:
    return CommentService(session)


@pytest.fixture()
def inbox(session: Session) -> NotificationService:
    return NotificationService(session)


def received(session: Session, person: User) -> list[tuple[NotificationKind, uuid.UUID | None]]:
    """What one person was told, oldest first: (kind, actor)."""
    rows = session.scalars(
        select(Notification)
        .where(Notification.recipient_id == person.id)
        .order_by(Notification.created_at, Notification.id)
    ).all()
    return [(row.kind, row.actor_id) for row in rows]


def watching(session: Session, task: Task) -> set[uuid.UUID]:
    return set(session.scalars(select(TaskWatcher.user_id).where(TaskWatcher.task_id == task.id)))


def mention(person: User) -> str:
    return f"<@{person.id}>"


# --- watching ----------------------------------------------------------------
def test_the_creator_and_the_assignee_watch_a_new_task(
    tasks: TaskService, cast: Cast, session: Session
) -> None:
    task = tasks.create_task(
        cast.team.id, TaskCreate(title="Ship", assignee_id=cast.mo.id), actor=cast.olive
    )

    assert watching(session, task) == {cast.olive.id, cast.mo.id}


def test_commenting_makes_you_watch(
    tasks: TaskService, comments: CommentService, cast: Cast, session: Session
) -> None:
    task = tasks.create_task(cast.team.id, TaskCreate(title="Talk"), actor=cast.olive)

    comments.add_comment(task.id, CommentCreate(body="Me too"), actor=cast.pat)

    assert cast.pat.id in watching(session, task)


def test_watching_is_idempotent_and_can_be_stopped(
    tasks: TaskService, inbox: NotificationService, cast: Cast
) -> None:
    task = tasks.create_task(cast.team.id, TaskCreate(title="Follow"), actor=cast.olive)

    inbox.watch(task.id, actor=cast.mo)
    people, me = inbox.watch(task.id, actor=cast.mo)
    assert me is True
    assert [person.id for person in people].count(cast.mo.id) == 1

    inbox.unwatch(task.id, actor=cast.mo)
    inbox.unwatch(task.id, actor=cast.mo)
    assert inbox.watchers(task.id, actor=cast.mo)[1] is False


def test_outsiders_cannot_see_or_join_a_tasks_watchers(
    tasks: TaskService, inbox: NotificationService, cast: Cast
) -> None:
    task = tasks.create_task(cast.team.id, TaskCreate(title="Private"), actor=cast.olive)

    with pytest.raises(TaskNotFoundError):
        inbox.watchers(task.id, actor=cast.oz)
    with pytest.raises(TaskNotFoundError):
        inbox.watch(task.id, actor=cast.oz)


def test_watching_stays_possible_while_a_company_is_suspended(
    tasks: TaskService, inbox: NotificationService, cast: Cast
) -> None:
    """It is the person's own setting, not the company's content."""
    task = tasks.create_task(cast.team.id, TaskCreate(title="Frozen"), actor=cast.olive)
    cast.workspaces.set_suspended(cast.team.id, suspended=True, note=None)

    assert inbox.watch(task.id, actor=cast.mo)[1] is True


# --- assigned ----------------------------------------------------------------
def test_being_assigned_by_someone_else_is_a_notification(
    tasks: TaskService, cast: Cast, session: Session
) -> None:
    task = tasks.create_task(cast.team.id, TaskCreate(title="Yours"), actor=cast.olive)

    tasks.update_task(task.id, TaskUpdate(assignee_id=cast.mo.id), actor=cast.olive)

    assert received(session, cast.mo) == [(NotificationKind.ASSIGNED, cast.olive.id)]
    assert received(session, cast.olive) == []


def test_assigning_yourself_tells_nobody(
    tasks: TaskService, cast: Cast, session: Session
) -> None:
    tasks.create_task(
        cast.team.id, TaskCreate(title="Mine", assignee_id=cast.mo.id), actor=cast.mo
    )

    assert received(session, cast.mo) == []


def test_saving_the_same_assignee_again_tells_nobody_twice(
    tasks: TaskService, cast: Cast, session: Session
) -> None:
    task = tasks.create_task(
        cast.team.id, TaskCreate(title="Again", assignee_id=cast.mo.id), actor=cast.olive
    )

    tasks.update_task(task.id, TaskUpdate(assignee_id=cast.mo.id), actor=cast.olive)

    assert received(session, cast.mo) == [(NotificationKind.ASSIGNED, cast.olive.id)]


def test_a_refused_save_tells_nobody(tasks: TaskService, cast: Cast, session: Session) -> None:
    task = tasks.create_task(cast.team.id, TaskCreate(title="Race"), actor=cast.pat)
    tasks.update_task(task.id, TaskUpdate(title="First"), actor=cast.pat)

    with pytest.raises(TaskConflictError):
        tasks.update_task(
            task.id, TaskUpdate(assignee_id=cast.mo.id, version=1), actor=cast.olive
        )

    assert received(session, cast.mo) == []
    assert cast.mo.id not in watching(session, task)


# --- commented and mentioned ---------------------------------------------------
def test_watchers_hear_about_a_comment_except_its_author(
    tasks: TaskService, comments: CommentService, cast: Cast, session: Session
) -> None:
    task = tasks.create_task(
        cast.team.id, TaskCreate(title="Thread", assignee_id=cast.mo.id), actor=cast.olive
    )

    comments.add_comment(task.id, CommentCreate(body="Update?"), actor=cast.olive)

    assert received(session, cast.mo)[-1] == (NotificationKind.COMMENTED, cast.olive.id)
    assert received(session, cast.olive) == []
    assert received(session, cast.pat) == []  # not watching


def test_a_mention_replaces_the_comment_notification(
    tasks: TaskService, comments: CommentService, cast: Cast, session: Session
) -> None:
    task = tasks.create_task(
        cast.team.id, TaskCreate(title="Ping", assignee_id=cast.mo.id), actor=cast.olive
    )

    comments.add_comment(
        task.id,
        CommentCreate(body=f"{mention(cast.mo)} and {mention(cast.pat)}, please look"),
        actor=cast.olive,
    )

    # Mo watches *and* is mentioned: one notification, the more specific one.
    assert received(session, cast.mo)[1:] == [(NotificationKind.MENTIONED, cast.olive.id)]
    assert received(session, cast.pat) == [(NotificationKind.MENTIONED, cast.olive.id)]
    # Being mentioned makes you watch.
    assert cast.pat.id in watching(session, task)


def test_mentioning_outsiders_or_yourself_tells_nobody(
    tasks: TaskService, comments: CommentService, cast: Cast, session: Session
) -> None:
    task = tasks.create_task(cast.team.id, TaskCreate(title="Quiet"), actor=cast.olive)

    comments.add_comment(
        task.id,
        CommentCreate(body=f"{mention(cast.oz)} {mention(cast.olive)} <@{uuid.uuid4()}>"),
        actor=cast.olive,
    )

    assert received(session, cast.oz) == []
    assert received(session, cast.olive) == []
    assert cast.oz.id not in watching(session, task)


def test_an_edit_tells_only_the_newly_mentioned(
    tasks: TaskService, comments: CommentService, cast: Cast, session: Session
) -> None:
    task = tasks.create_task(cast.team.id, TaskCreate(title="Edit"), actor=cast.olive)
    comment = comments.add_comment(
        task.id, CommentCreate(body=f"cc {mention(cast.mo)}"), actor=cast.olive
    )

    comments.edit_comment(
        comment.id,
        CommentUpdate(body=f"cc {mention(cast.mo)} {mention(cast.pat)}"),
        actor=cast.olive,
    )

    assert received(session, cast.mo) == [(NotificationKind.MENTIONED, cast.olive.id)]
    assert received(session, cast.pat) == [(NotificationKind.MENTIONED, cast.olive.id)]


def test_deleting_a_comment_removes_it_from_every_inbox(
    tasks: TaskService, comments: CommentService, cast: Cast, session: Session
) -> None:
    task = tasks.create_task(cast.team.id, TaskCreate(title="Oops"), actor=cast.olive)
    comment = comments.add_comment(
        task.id, CommentCreate(body=f"{mention(cast.mo)} secret"), actor=cast.olive
    )

    comments.delete_comment(comment.id, actor=cast.olive)

    assert received(session, cast.mo) == []


def test_deleting_a_task_removes_its_watchers_and_notifications(
    tasks: TaskService, cast: Cast, session: Session
) -> None:
    task = tasks.create_task(
        cast.team.id, TaskCreate(title="Gone", assignee_id=cast.mo.id), actor=cast.olive
    )

    tasks.delete_task(task.id, actor=cast.olive)

    assert watching(session, task) == set()
    assert received(session, cast.mo) == []


# --- leaving -------------------------------------------------------------------
def test_leaving_a_company_empties_your_inbox_and_watches_of_it_only(
    tasks: TaskService, cast: Cast, session: Session
) -> None:
    here = tasks.create_task(
        cast.team.id, TaskCreate(title="Here", assignee_id=cast.mo.id), actor=cast.olive
    )
    elsewhere = cast.workspaces.create_team(
        WorkspaceCreate(name="Else Co", slug=slug_for("bell-else")), actor=cast.olive
    )
    invite = cast.workspaces.invite(
        elsewhere.id, InviteCreate(user_id=cast.mo.id), actor=cast.olive
    )
    cast.workspaces.accept_invitation(invite.id, actor=cast.mo)
    there = tasks.create_task(
        elsewhere.id, TaskCreate(title="There", assignee_id=cast.mo.id), actor=cast.olive
    )

    cast.workspaces.remove_member(cast.team.id, cast.mo.id, actor=cast.mo)

    assert cast.mo.id not in watching(session, here)
    assert cast.mo.id in watching(session, there)
    tasks_told = session.scalars(
        select(Notification.task_id).where(Notification.recipient_id == cast.mo.id)
    ).all()
    assert tasks_told == [there.id]


def test_the_inbox_rechecks_membership_on_every_read(
    tasks: TaskService, inbox: NotificationService, cast: Cast, session: Session
) -> None:
    """Even a row left behind by some other path never shows a former company."""
    tasks.create_task(
        cast.team.id, TaskCreate(title="Left behind", assignee_id=cast.mo.id), actor=cast.olive
    )
    membership = workspace_repository.get_member(session, cast.team.id, cast.mo.id)
    assert membership is not None
    workspace_repository.remove_member(session, membership)  # no cleanup on purpose
    session.commit()

    rows, total, _pages, unread = inbox.inbox(actor=cast.mo)

    assert (rows, total, unread) == ([], 0, 0)


# --- the inbox -----------------------------------------------------------------
def test_the_inbox_is_newest_first_with_an_unread_count(
    tasks: TaskService, comments: CommentService, inbox: NotificationService, cast: Cast
) -> None:
    task = tasks.create_task(
        cast.team.id, TaskCreate(title="Busy", assignee_id=cast.mo.id), actor=cast.olive
    )
    comments.add_comment(task.id, CommentCreate(body="First"), actor=cast.pat)

    rows, total, _pages, unread = inbox.inbox(actor=cast.mo)

    assert (total, unread) == (2, 2)
    assert [row.kind for row, _excerpt in rows] == [
        NotificationKind.COMMENTED,
        NotificationKind.ASSIGNED,
    ]
    assert rows[0][1] == "First"
    assert rows[1][1] is None


def test_excerpts_show_mentions_by_name_and_stay_short(
    tasks: TaskService, comments: CommentService, inbox: NotificationService, cast: Cast
) -> None:
    task = tasks.create_task(cast.team.id, TaskCreate(title="Long"), actor=cast.olive)
    comments.add_comment(
        task.id,
        CommentCreate(body=f"Hey {mention(cast.mo)},\n\n" + "word " * 60),
        actor=cast.olive,
    )

    [(row, excerpt)] = inbox.inbox(actor=cast.mo)[0]

    assert excerpt is not None
    assert excerpt.startswith("Hey @Mo Member, word word")
    assert len(excerpt) == 140 and excerpt.endswith("…")
    assert str(cast.mo.id) not in excerpt


def test_marking_read_is_private_to_the_recipient(
    tasks: TaskService, inbox: NotificationService, cast: Cast
) -> None:
    tasks.create_task(
        cast.team.id, TaskCreate(title="Mine to read", assignee_id=cast.mo.id), actor=cast.olive
    )
    [(row, _excerpt)] = inbox.inbox(actor=cast.mo)[0]

    with pytest.raises(NotificationNotFoundError):
        inbox.mark_read(row.id, actor=cast.pat)
    with pytest.raises(NotificationNotFoundError):
        inbox.mark_read(uuid.uuid4(), actor=cast.mo)

    inbox.mark_read(row.id, actor=cast.mo)
    inbox.mark_read(row.id, actor=cast.mo)  # already read is fine
    assert inbox.unread_count(actor=cast.mo) == 0


def test_mark_all_read(
    tasks: TaskService, comments: CommentService, inbox: NotificationService, cast: Cast
) -> None:
    task = tasks.create_task(
        cast.team.id, TaskCreate(title="Many", assignee_id=cast.mo.id), actor=cast.olive
    )
    comments.add_comment(task.id, CommentCreate(body="One"), actor=cast.pat)

    assert inbox.mark_all_read(actor=cast.mo) == 2
    assert inbox.unread_count(actor=cast.mo) == 0
    assert inbox.inbox(actor=cast.mo, unread_only=True)[1] == 0


def test_the_database_refuses_a_notification_to_its_own_actor(
    tasks: TaskService, cast: Cast, session: Session
) -> None:
    task = tasks.create_task(cast.team.id, TaskCreate(title="Self"), actor=cast.olive)

    session.add(
        Notification(
            kind=NotificationKind.ASSIGNED,
            recipient_id=cast.olive.id,
            actor_id=cast.olive.id,
            workspace_id=cast.team.id,
            task_id=task.id,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
