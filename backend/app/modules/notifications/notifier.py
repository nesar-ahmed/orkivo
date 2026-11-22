"""How other modules tell people about changes.

A service that makes a change builds a ``Notifier`` on *its own* session and
calls it before committing, exactly like ``activity.recorder.ActivityRecorder``.
The notifier never flushes a notification or commits, so a refused or
rolled-back change tells nobody anything, and a committed one is never missing
its notifications (architecture doc section 6.2).

The rules, in one place:

* **Watching.** Creating a task, being assigned it, commenting on it and being
  mentioned in it all make a person watch it.
* **Assigned.** The new assignee is told --- unless they assigned themselves.
* **Commented.** Every watcher is told, except the author and anyone the comment
  mentions (they get ``mentioned`` instead: one notification per comment each).
* **Mentioned.** Each person a comment mentions is told, if they are a member of
  the task's workspace *now*. Editing a comment tells only people it newly
  mentions.
* **Unblocked.** When the last unfinished task blocking a task is done, that
  task's assignee is told it is ready to start --- unless they did it themselves.
* **Completed.** When a task is moved to Done, the people the workspace's
  automation rules name are told (``automations.runner``): once each, however
  many rules name them, and never the person who finished it.

Nobody is ever told about their own action, and nobody outside the workspace is
ever told anything: recipients are filtered through the access policy.
"""

import uuid
from collections.abc import Collection, Iterable

from sqlalchemy.orm import Session

from app.modules.notifications import repository
from app.modules.notifications.enums import NotificationKind
from app.modules.notifications.models import Notification
from app.modules.tasks.models import Task
from app.modules.users.models import User
from app.modules.workspaces.access import WorkspaceAccessPolicy


class Notifier:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._access = WorkspaceAccessPolicy(session)

    def watch(self, task: Task, people: Iterable[User]) -> None:
        """Make these people follow the task. Idempotent."""
        repository.add_watchers(self._session, task.id, [person.id for person in people])

    def task_assigned(self, task: Task, *, assignee: User, actor: User) -> None:
        """The assignee now follows the task, and is told unless they did it."""
        self.watch(task, [assignee])
        if assignee.id != actor.id:
            self._notify(NotificationKind.ASSIGNED, task, {assignee.id}, actor=actor)

    def task_unblocked(self, task: Task, *, assignee: User, actor: User) -> None:
        """Nothing open blocks ``task`` any more: its assignee hears it is ready."""
        self.watch(task, [assignee])
        self._notify(NotificationKind.UNBLOCKED, task, {assignee.id}, actor=actor)

    def task_completed(
        self,
        task: Task,
        *,
        actor: User,
        people: Collection[uuid.UUID],
        include_watchers: bool = False,
    ) -> list[User]:
        """``task`` was moved to Done: tell ``people`` (and its watchers), once each.

        Unlike an assignment, this does not make anyone watch the task: a rule
        telling the workspace's owners about every finished task must not sign
        them up for every comment on it. Returns who was told, alphabetically.
        """
        recipients = set(people)
        if include_watchers:
            recipients |= repository.watcher_ids(self._session, task.id)
        return self._notify(NotificationKind.COMPLETED, task, recipients, actor=actor)

    def comment_added(
        self,
        task: Task,
        comment_id: uuid.UUID,
        *,
        actor: User,
        mentioned: Collection[User],
    ) -> None:
        """Watchers hear about a new comment; the people it mentions hear more."""
        self.watch(task, [actor, *mentioned])
        mentioned_ids = {person.id for person in mentioned} - {actor.id}
        watchers = repository.watcher_ids(self._session, task.id) - {actor.id} - mentioned_ids
        self._notify(
            NotificationKind.MENTIONED, task, mentioned_ids, actor=actor, comment_id=comment_id
        )
        self._notify(
            NotificationKind.COMMENTED, task, watchers, actor=actor, comment_id=comment_id
        )

    def comment_edited(
        self,
        task: Task,
        comment_id: uuid.UUID,
        *,
        actor: User,
        newly_mentioned: Collection[User],
    ) -> None:
        """An edit tells only the people it mentions for the first time."""
        self.watch(task, newly_mentioned)
        self._notify(
            NotificationKind.MENTIONED,
            task,
            {person.id for person in newly_mentioned} - {actor.id},
            actor=actor,
            comment_id=comment_id,
        )

    def _notify(
        self,
        kind: NotificationKind,
        task: Task,
        recipient_ids: Collection[uuid.UUID],
        *,
        actor: User,
        comment_id: uuid.UUID | None = None,
    ) -> list[User]:
        """One notification per recipient who is still a member, never the actor.

        Returns who was actually told, by name, for callers that record it.
        """
        wanted = set(recipient_ids) - {actor.id}
        if not wanted:
            return []
        members = self._access.members_among(task.workspace_id, wanted)
        for recipient_id in sorted(members, key=str):
            repository.add_notification(
                self._session,
                Notification(
                    kind=kind,
                    recipient_id=recipient_id,
                    workspace_id=task.workspace_id,
                    task_id=task.id,
                    comment_id=comment_id,
                    actor=actor,
                ),
            )
        return sorted(members.values(), key=lambda person: (person.display_name, str(person.id)))
