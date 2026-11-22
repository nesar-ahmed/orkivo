"""Application service for the inbox and for watching tasks.

Notifications are *created* by ``notifier.Notifier``, inside the transactions
of the changes they announce; this service reads them and lets their recipient
mark them read, and lets a member follow or stop following a task.

An inbox is private: another person's notification reads as not found. Watching
is reached exactly like the task (``TaskService.authorized_task``, ``read``):
it is the person's own setting rather than the company's content, so it stays
available while a company is suspended --- as does marking notifications read.
"""

import math
import uuid
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.modules.comments.mentions import mentioned_ids, plain_text
from app.modules.notifications import repository
from app.modules.notifications.exceptions import NotificationNotFoundError
from app.modules.notifications.models import Notification
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from app.modules.workspaces.access import WorkspaceAccessPolicy
from app.modules.workspaces.enums import WorkspaceAction
from app.shared.time import utc_now

#: How much of a comment an inbox row shows.
EXCERPT_LENGTH = 140


class NotificationService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._access = WorkspaceAccessPolicy(session)
        self._tasks = TaskService(session)

    # --- the inbox -----------------------------------------------------------
    def inbox(
        self, *, actor: User, unread_only: bool = False, page: int = 1, page_size: int = 20
    ) -> tuple[list[tuple[Notification, str | None]], int, int, int]:
        """One page of the caller's inbox with comment excerpts, and the unread count."""
        items, total = repository.list_inbox(
            self._session,
            recipient_id=actor.id,
            unread_only=unread_only,
            page=page,
            page_size=page_size,
        )
        rows = [(item, self._excerpt(item)) for item in items]
        unread = repository.count_unread(self._session, actor.id)
        return rows, total, _pages(total, page, page_size), unread

    def unread_count(self, *, actor: User) -> int:
        return repository.count_unread(self._session, actor.id)

    def mark_read(self, notification_id: uuid.UUID, *, actor: User) -> None:
        """Mark one of the caller's notifications read. Already read is fine."""
        notification = repository.get_notification(self._session, notification_id)
        if notification is None or notification.recipient_id != actor.id:
            raise NotificationNotFoundError(notification_id)
        if notification.read_at is None:
            notification.read_at = utc_now()
            self._commit()

    def mark_all_read(self, *, actor: User) -> int:
        count = repository.mark_all_read(self._session, actor.id)
        self._commit()
        return count

    # --- watching ------------------------------------------------------------
    def watchers(self, task_id: uuid.UUID, *, actor: User) -> tuple[Sequence[User], bool]:
        """Who follows a task, and whether the caller does."""
        task = self._tasks.authorized_task(task_id, actor=actor, action=WorkspaceAction.READ)
        people = repository.list_watchers(self._session, task.id)
        return people, any(person.id == actor.id for person in people)

    def watch(self, task_id: uuid.UUID, *, actor: User) -> tuple[Sequence[User], bool]:
        task = self._tasks.authorized_task(task_id, actor=actor, action=WorkspaceAction.READ)
        repository.add_watchers(self._session, task.id, [actor.id])
        self._commit()
        return self.watchers(task_id, actor=actor)

    def unwatch(self, task_id: uuid.UUID, *, actor: User) -> None:
        task = self._tasks.authorized_task(task_id, actor=actor, action=WorkspaceAction.READ)
        repository.remove_watcher(self._session, task.id, actor.id)
        self._commit()

    # --- helpers -----------------------------------------------------------
    def _excerpt(self, notification: Notification) -> str | None:
        """The start of the comment, with mentions shown by current members' names."""
        comment = notification.comment
        if comment is None:
            return None
        names = {
            person_id: account.display_name
            for person_id, account in self._access.members_among(
                notification.workspace_id, mentioned_ids(comment.body)
            ).items()
        }
        text = " ".join(plain_text(comment.body, names).split())
        return text if len(text) <= EXCERPT_LENGTH else f"{text[: EXCERPT_LENGTH - 1]}…"

    def _commit(self) -> None:
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise


def _pages(total: int, page: int, page_size: int) -> int:
    """Page count for the collection envelope."""
    return math.ceil(total / page_size) if total else 0
