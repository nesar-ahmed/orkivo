"""What the tasks module does when someone's membership of a workspace ends.

The ``workspaces`` module owns membership and decides *whether* a person may
leave or be removed; it does not own the work stored in the tenant (architecture
doc section 5). This is the tasks module's public answer to "this person is no
longer here", so the workspaces service never reads or writes the tasks tables
itself.

It runs inside the caller's transaction and never commits: the membership row,
everything released here, and the activity events describing it are one unit of
work, so no database state ever shows a departed member still holding a
company's tasks, or a release the log does not mention (section 6.2).
"""

import uuid
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.modules.activity.enums import ActivityVerb
from app.modules.activity.recorder import ActivityRecorder
from app.modules.tasks import history, repository
from app.modules.users.models import User


def release_member(
    session: Session, *, workspace_id: uuid.UUID, user_id: uuid.UUID, actor: User
) -> Sequence[uuid.UUID]:
    """Unassign ``user_id`` from every task in ``workspace_id``; return those tasks.

    ``actor`` is whoever ended the membership --- the person leaving, or the
    owner or admin who removed them --- and is recorded as the tasks' editor and
    as the actor of each task's ``task.updated`` event.
    """
    departing = history.person(session.get(User, user_id))
    released = repository.unassign_member(
        session, workspace_id=workspace_id, user_id=user_id, actor_id=actor.id
    )
    recorder = ActivityRecorder(session)
    for task in released:
        recorder.record(
            ActivityVerb.TASK_UPDATED,
            workspace_id=task.workspace_id,
            actor=actor,
            task_id=task.id,
            task_title=task.title,
            task_version=task.version,
            changes={"assignee": {"from": departing, "to": None}},
        )
    return [task.id for task in released]
