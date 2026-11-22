"""Application service implementing comment use cases.

Business rules live here, not in route handlers. Transaction boundaries are
committed at this use-case layer and rolled back on failure (architecture doc
section 6.2).

A comment inherits its task's access rule, through the same code path:

==========================  ================  ==================================
Use case                    Action            And also
==========================  ================  ==================================
Read a task's comments      ``read``          ---
Comment                     ``comment``       ---
Edit a comment              ``comment``       only its author
Delete a comment            ``comment``       its author, or an owner or admin
==========================  ================  ==================================

So a suspended company's conversations stay readable and frozen, a viewer reads
along without taking part, and a comment on a task the caller cannot see reads as
not found. Commenting is its own action rather than part of changing tasks: a
member may discuss any task they can read, including ones they may not change.

Every change is written to the activity log in the same transaction, and so are
the notifications it causes: watchers hear about a new comment, and people it
mentions (``<@user-id>``, see ``mentions``) hear that they were mentioned --- on
an edit, only people mentioned for the first time. Mentions resolve to *current
members* of the task's workspace only, for notifying and for display alike. The
log records *that* a comment was added, edited or deleted, never its text:
deleting a comment must actually remove what it said, and an append-only log
cannot be cleaned afterwards.
"""

import math
import uuid
from collections.abc import Callable, Mapping, Sequence

from sqlalchemy.orm import Session

from app.modules.activity.enums import ActivityVerb
from app.modules.activity.recorder import ActivityRecorder
from app.modules.comments import repository
from app.modules.comments.exceptions import CommentForbiddenError, CommentNotFoundError
from app.modules.comments.mentions import mentioned_ids
from app.modules.comments.models import TaskComment
from app.modules.comments.schemas import CommentCreate, CommentUpdate
from app.modules.notifications.notifier import Notifier
from app.modules.tasks.models import Task
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from app.modules.workspaces.access import WorkspaceAccess, WorkspaceAccessPolicy
from app.modules.workspaces.enums import WorkspaceAction
from app.shared.time import utc_now


class CommentService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._access = WorkspaceAccessPolicy(session)
        self._tasks = TaskService(session)
        self._recorder = ActivityRecorder(session)
        self._notifier = Notifier(session)

    # --- one task's conversation ---------------------------------------------
    def list_comments(
        self, task_id: uuid.UUID, *, actor: User, page: int = 1, page_size: int = 20
    ) -> tuple[Sequence[TaskComment], int, int]:
        task = self._tasks.authorized_task(task_id, actor=actor, action=WorkspaceAction.READ)
        items, total = repository.list_comments(
            self._session,
            workspace_id=task.workspace_id,
            task_id=task.id,
            page=page,
            page_size=page_size,
        )
        return items, total, _pages(total, page, page_size)

    def add_comment(self, task_id: uuid.UUID, data: CommentCreate, *, actor: User) -> TaskComment:
        task = self._tasks.authorized_task(task_id, actor=actor, action=WorkspaceAction.COMMENT)
        comment = TaskComment(
            task_id=task.id, workspace_id=task.workspace_id, author=actor, body=data.body
        )
        repository.add_comment(self._session, comment)
        mentioned = self._mentioned(task, comment.body)

        def record_and_notify() -> None:
            self._record(ActivityVerb.COMMENT_ADDED, task, comment.id, actor=actor)
            self._notifier.comment_added(task, comment.id, actor=actor, mentioned=mentioned)

        self._commit(then=record_and_notify)
        return comment

    # --- one comment ---------------------------------------------------------
    def edit_comment(
        self, comment_id: uuid.UUID, data: CommentUpdate, *, actor: User
    ) -> TaskComment:
        """Replace the text. The author only; unchanged text changes nothing."""
        comment, _access = self._authorized_comment(comment_id, actor=actor)
        if comment.author_id != actor.id:
            raise CommentForbiddenError
        if data.body == comment.body:
            return comment
        already = set(mentioned_ids(comment.body))
        comment.body = data.body
        comment.edited_at = utc_now()
        self._session.flush()
        task = comment.task
        newly = [person for person in self._mentioned(task, data.body) if person.id not in already]

        def record_and_notify() -> None:
            self._record(ActivityVerb.COMMENT_EDITED, task, comment.id, actor=actor)
            self._notifier.comment_edited(task, comment.id, actor=actor, newly_mentioned=newly)

        self._commit(then=record_and_notify)
        return comment

    def delete_comment(self, comment_id: uuid.UUID, *, actor: User) -> None:
        """Remove a comment: its author, or an owner or admin moderating."""
        comment, access = self._authorized_comment(comment_id, actor=actor)
        if comment.author_id != actor.id and not access.allows(WorkspaceAction.MANAGE):
            raise CommentForbiddenError
        task = comment.task
        repository.delete_comment(self._session, comment)
        self._session.flush()
        self._commit(
            then=lambda: self._record(ActivityVerb.COMMENT_DELETED, task, comment_id, actor=actor)
        )

    def mentions_in(self, comments: Sequence[TaskComment]) -> Mapping[uuid.UUID, User]:
        """The people these comments mention who are members of their workspace now.

        One lookup per workspace for a whole page, for rendering ``<@id>`` as a
        name. Someone who has since left is simply absent, and reads as
        "@someone" rather than leaking who they were.
        """
        found: dict[uuid.UUID, User] = {}
        by_workspace: dict[uuid.UUID, set[uuid.UUID]] = {}
        for comment in comments:
            by_workspace.setdefault(comment.workspace_id, set()).update(
                mentioned_ids(comment.body)
            )
        for workspace_id, ids in by_workspace.items():
            found.update(self._access.members_among(workspace_id, ids))
        return found

    # --- helpers -----------------------------------------------------------
    def _mentioned(self, task: Task, body: str) -> list[User]:
        """The members a body mentions, in order of first mention."""
        ids = mentioned_ids(body)
        members = self._access.members_among(task.workspace_id, ids)
        return [members[person_id] for person_id in ids if person_id in members]

    def _authorized_comment(
        self, comment_id: uuid.UUID, *, actor: User
    ) -> tuple[TaskComment, WorkspaceAccess]:
        """The comment, once the caller may take part in its workspace's conversations.

        A missing comment and one on a task the caller cannot see both raise
        ``CommentNotFoundError`` with the same payload.
        """
        comment = repository.get_comment(self._session, comment_id)
        if comment is None:
            raise CommentNotFoundError(comment_id)
        access = self._access.require_for_content(
            comment.workspace_id,
            actor=actor,
            action=WorkspaceAction.COMMENT,
            hidden_as=CommentNotFoundError(comment_id),
        )
        return comment, access

    def _record(
        self, verb: ActivityVerb, task: Task, comment_id: uuid.UUID, *, actor: User
    ) -> None:
        """One event on the task's history, without the comment's text."""
        self._recorder.record(
            verb,
            workspace_id=task.workspace_id,
            actor=actor,
            task_id=task.id,
            task_title=task.title,
            task_version=task.version,
            comment_id=comment_id,
        )

    def _commit(self, *, then: Callable[[], None] | None = None) -> None:
        """Record the event (``then``) and commit, as one step: on any failure the
        comment change is rolled back with its event."""
        try:
            if then is not None:
                then()
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise


def _pages(total: int, page: int, page_size: int) -> int:
    """Page count for the collection envelope."""
    return math.ceil(total / page_size) if total else 0
