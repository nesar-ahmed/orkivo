"""What the task dependencies module offers the tasks module.

The ``tasks`` module owns tasks; it does not own which of them wait on which
(architecture doc section 5). These functions are this module's public answer
to "how many open tasks still block these tasks?" --- shown on every task the API
returns --- and "these tasks are done", so the tasks service never reads the
``task_dependencies`` table itself.

Neither commits. ``task_finished`` runs inside the tasks service's own
transaction, after the save is flushed, so a save refused with ``409`` tells
nobody anything and a committed one is never missing its notifications
(section 6.2).
"""

import uuid
from collections.abc import Collection, Mapping, Sequence

from sqlalchemy.orm import Session

from app.modules.notifications.notifier import Notifier
from app.modules.task_dependencies import repository
from app.modules.tasks.models import Task
from app.modules.users.models import User


def open_blocker_counts(
    session: Session, task_ids: Collection[uuid.UUID]
) -> Mapping[uuid.UUID, int]:
    """How many unfinished tasks each of ``task_ids`` waits on; zero when none."""
    found = repository.open_blocker_counts(session, task_ids)
    return {task_id: found.get(task_id, 0) for task_id in task_ids}


def task_finished(session: Session, task: Task, *, actor: User) -> None:
    """``task`` was just marked done: tell whoever it was the last thing blocking."""
    tasks_finished(session, [task], actor=actor)


def tasks_finished(session: Session, tasks: Sequence[Task], *, actor: User) -> None:
    """``tasks`` were just marked done, together: tell whoever they unblocked, once.

    Each task that waited on any of them, is not done itself and now waits on
    nothing open is *ready to start*; its assignee is told so, unless they
    finished the blocker themselves. An unassigned task tells nobody --- there is
    no one whose work just became possible.

    Finishing several blockers of the same task at once (a bulk "mark done") makes
    it ready once, not once per blocker: every one of them is already flushed as
    done when this runs, so each would otherwise look like "the last one".
    """
    notifier = Notifier(session)
    ready: dict[uuid.UUID, Task] = {}
    for finished in tasks:
        for waiting in repository.unblocked_by(session, finished):
            ready.setdefault(waiting.id, waiting)
    for waiting in ready.values():
        if waiting.assignee is not None:
            notifier.task_unblocked(waiting, assignee=waiting.assignee, actor=actor)
