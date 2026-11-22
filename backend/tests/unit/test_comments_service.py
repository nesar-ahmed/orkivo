"""Unit tests for comments (service rules, without HTTP).

A comment inherits its task's access rule, and adds two of its own: only the
author edits it, and its author or an owner or admin deletes it. Commenting never
changes the task's version, and the activity log records that a comment changed
--- never what it said (architecture doc sections 6 and 9).
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.activity.enums import ActivityVerb
from app.modules.activity.models import ActivityEvent
from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.comments.exceptions import CommentForbiddenError, CommentNotFoundError
from app.modules.comments.models import TaskComment
from app.modules.comments.schemas import CommentCreate, CommentUpdate
from app.modules.comments.service import CommentService
from app.modules.tasks.exceptions import TaskNotFoundError
from app.modules.tasks.models import Task
from app.modules.tasks.schemas import TaskCreate
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from app.modules.workspaces.enums import WorkspaceRole
from app.modules.workspaces.exceptions import WorkspaceSuspendedError
from app.modules.workspaces.schemas import InviteCreate, WorkspaceCreate
from app.modules.workspaces.service import WorkspaceService
from tests.synth import PASSWORD, email_for, slug_for

pytestmark = pytest.mark.unit


def _register(accounts: AuthService, label: str) -> User:
    return accounts.register(RegisterRequest(email=email_for(label), password=PASSWORD))


class Cast:
    """A company with an owner, an admin and two members, one task, and an outsider."""

    def __init__(self, session: Session) -> None:
        accounts = AuthService(session)
        self.workspaces = WorkspaceService(session)
        self.owner = _register(accounts, "talk-owner")
        self.admin = _register(accounts, "talk-admin")
        self.member = _register(accounts, "talk-member")
        self.other = _register(accounts, "talk-other")
        self.outsider = _register(accounts, "talk-outsider")
        self.team = self.workspaces.create_team(
            WorkspaceCreate(name="Talk Co", slug=slug_for("talk")), actor=self.owner
        )
        for account, role in (
            (self.admin, WorkspaceRole.ADMIN),
            (self.member, WorkspaceRole.MEMBER),
            (self.other, WorkspaceRole.MEMBER),
        ):
            invite = self.workspaces.invite(
                self.team.id, InviteCreate(user_id=account.id, role=role), actor=self.owner
            )
            self.workspaces.accept_invitation(invite.id, actor=account)
        self.task = TaskService(session).create_task(
            self.team.id, TaskCreate(title="Discuss me"), actor=self.owner
        )


@pytest.fixture()
def cast(session: Session) -> Cast:
    return Cast(session)


@pytest.fixture()
def comments(session: Session) -> CommentService:
    return CommentService(session)


def comment_events(session: Session) -> list[ActivityEvent]:
    return list(
        session.scalars(
            select(ActivityEvent)
            .where(ActivityEvent.verb.in_([v for v in ActivityVerb if v.startswith("comment.")]))
            .order_by(ActivityEvent.created_at, ActivityEvent.id)
        ).all()
    )


# --- writing -----------------------------------------------------------------
def test_any_member_can_comment_without_touching_the_task_version(
    comments: CommentService, cast: Cast, session: Session
) -> None:
    comment = comments.add_comment(
        cast.task.id, CommentCreate(body="  Looks good to me  "), actor=cast.member
    )

    assert comment.body == "Looks good to me"
    assert comment.author is not None and comment.author.id == cast.member.id
    assert (comment.task_id, comment.workspace_id) == (cast.task.id, cast.team.id)
    assert comment.edited_at is None
    # Talking about a task is not editing it: nobody's open save can conflict.
    session.expire_all()
    task = session.get(Task, cast.task.id)
    assert task is not None and task.version == 1


def test_comments_read_oldest_first(comments: CommentService, cast: Cast) -> None:
    for body in ("first", "second", "third"):
        comments.add_comment(cast.task.id, CommentCreate(body=body), actor=cast.member)

    items, total, pages = comments.list_comments(cast.task.id, actor=cast.owner, page_size=2)

    assert (total, pages) == (3, 2)
    assert [c.body for c in items] == ["first", "second"]


def test_outsiders_cannot_read_or_write_the_conversation(
    comments: CommentService, cast: Cast
) -> None:
    comment = comments.add_comment(cast.task.id, CommentCreate(body="Inside"), actor=cast.member)

    with pytest.raises(TaskNotFoundError):
        comments.list_comments(cast.task.id, actor=cast.outsider)
    with pytest.raises(TaskNotFoundError):
        comments.add_comment(cast.task.id, CommentCreate(body="Hi"), actor=cast.outsider)
    with pytest.raises(CommentNotFoundError):
        comments.edit_comment(comment.id, CommentUpdate(body="Mine"), actor=cast.outsider)
    with pytest.raises(CommentNotFoundError):
        comments.delete_comment(comment.id, actor=cast.outsider)


# --- editing -----------------------------------------------------------------
def test_only_the_author_edits_and_the_edit_is_marked(
    comments: CommentService, cast: Cast
) -> None:
    comment = comments.add_comment(cast.task.id, CommentCreate(body="Typo"), actor=cast.member)

    for someone in (cast.other, cast.admin, cast.owner):
        with pytest.raises(CommentForbiddenError):
            comments.edit_comment(comment.id, CommentUpdate(body="Not yours"), actor=someone)

    edited = comments.edit_comment(comment.id, CommentUpdate(body="Fixed"), actor=cast.member)
    assert edited.body == "Fixed"
    assert edited.edited_at is not None


def test_saving_the_same_text_changes_nothing(
    comments: CommentService, cast: Cast, session: Session
) -> None:
    comment = comments.add_comment(cast.task.id, CommentCreate(body="Stable"), actor=cast.member)

    same = comments.edit_comment(comment.id, CommentUpdate(body=" Stable "), actor=cast.member)

    assert same.edited_at is None
    assert [e.verb for e in comment_events(session)] == [ActivityVerb.COMMENT_ADDED]


# --- deleting ----------------------------------------------------------------
def test_the_author_or_a_manager_may_delete_but_not_another_member(
    comments: CommentService, cast: Cast, session: Session
) -> None:
    mine = comments.add_comment(cast.task.id, CommentCreate(body="Mine"), actor=cast.member)
    moderated = comments.add_comment(cast.task.id, CommentCreate(body="Rude"), actor=cast.member)
    owned = comments.add_comment(cast.task.id, CommentCreate(body="Off"), actor=cast.member)

    with pytest.raises(CommentForbiddenError):
        comments.delete_comment(mine.id, actor=cast.other)

    comments.delete_comment(mine.id, actor=cast.member)
    comments.delete_comment(moderated.id, actor=cast.admin)
    comments.delete_comment(owned.id, actor=cast.owner)

    assert comments.list_comments(cast.task.id, actor=cast.owner)[1] == 0


def test_deleting_a_task_deletes_its_conversation(
    comments: CommentService, cast: Cast, session: Session
) -> None:
    comments.add_comment(cast.task.id, CommentCreate(body="Gone soon"), actor=cast.member)

    TaskService(session).delete_task(cast.task.id, actor=cast.owner)

    assert session.scalars(select(TaskComment)).all() == []


# --- the log -----------------------------------------------------------------
def test_the_log_records_that_comments_changed_but_never_their_text(
    comments: CommentService, cast: Cast, session: Session
) -> None:
    comment = comments.add_comment(
        cast.task.id, CommentCreate(body="secret plan"), actor=cast.member
    )
    comments.edit_comment(comment.id, CommentUpdate(body="revised plan"), actor=cast.member)
    comments.delete_comment(comment.id, actor=cast.admin)

    logged = comment_events(session)
    assert [e.verb for e in logged] == [
        ActivityVerb.COMMENT_ADDED,
        ActivityVerb.COMMENT_EDITED,
        ActivityVerb.COMMENT_DELETED,
    ]
    assert {e.comment_id for e in logged} == {comment.id}
    assert [e.actor_id for e in logged] == [cast.member.id, cast.member.id, cast.admin.id]
    for event in logged:
        assert event.changes == {}
        assert "plan" not in repr(event.changes)
        assert (event.task_id, event.task_title) == (cast.task.id, "Discuss me")


# --- view mode ---------------------------------------------------------------
def test_a_suspended_company_keeps_its_conversations_readable_and_frozen(
    comments: CommentService, cast: Cast
) -> None:
    comment = comments.add_comment(cast.task.id, CommentCreate(body="Before"), actor=cast.member)
    cast.workspaces.set_suspended(cast.team.id, suspended=True, note=None)

    assert comments.list_comments(cast.task.id, actor=cast.member)[1] == 1
    with pytest.raises(WorkspaceSuspendedError):
        comments.add_comment(cast.task.id, CommentCreate(body="After"), actor=cast.member)
    with pytest.raises(WorkspaceSuspendedError):
        comments.edit_comment(comment.id, CommentUpdate(body="Changed"), actor=cast.member)
    with pytest.raises(WorkspaceSuspendedError):
        comments.delete_comment(comment.id, actor=cast.owner)
