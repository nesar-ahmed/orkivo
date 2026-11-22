"""What the tasks module offers the labels module.

The ``labels`` module owns label lifecycle; it does not own which tasks carry a
label (architecture doc section 5). These two functions are the tasks module's
public answer to "how many tasks carry these labels?" and "this label is going
away", so the labels service never reads or writes the ``task_labels`` table
itself --- the same arrangement as ``project_links`` for projects.

Neither function commits. Detaching runs inside the labels service's own
transaction --- with one activity event per task it changes --- so no database
state ever shows a task carrying a label that no longer exists, or a change the
log does not mention (section 6.2).
"""

import uuid
from collections.abc import Collection, Mapping, Sequence

from sqlalchemy.orm import Session

from app.modules.activity.enums import ActivityVerb
from app.modules.activity.recorder import ActivityRecorder
from app.modules.labels.models import Label
from app.modules.tasks import history, repository
from app.modules.users.models import User


def count_by_label(
    session: Session, label_ids: Collection[uuid.UUID]
) -> Mapping[uuid.UUID, int]:
    """How many tasks carry each of ``label_ids``; a label on no task counts zero."""
    found = repository.count_by_label(session, label_ids)
    return {label_id: found.get(label_id, 0) for label_id in label_ids}


def detach_label(session: Session, *, label: Label, actor: User) -> Sequence[uuid.UUID]:
    """Take ``label`` off every task that carries it; return the tasks changed.

    Each task keeps its other labels and is recorded as an edit by ``actor``, with
    a new version and a ``task.updated`` event whose ``labels`` change still names
    the label as it was.
    """
    carried = repository.labels_of_tasks_carrying(session, label.id)
    detached = repository.remove_label(
        session,
        workspace_id=label.workspace_id,
        label_id=label.id,
        task_ids=list(carried),
        actor_id=actor.id,
    )
    recorder = ActivityRecorder(session)
    for task in detached:
        before = carried[task.id]
        recorder.record(
            ActivityVerb.TASK_UPDATED,
            workspace_id=task.workspace_id,
            actor=actor,
            task_id=task.id,
            task_title=task.title,
            task_version=task.version,
            changes={
                "labels": {
                    "from": history.label_refs(list(before)),
                    "to": history.label_refs([kept for kept in before if kept.id != label.id]),
                }
            },
        )
    return [task.id for task in detached]
