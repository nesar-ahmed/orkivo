"""What the tasks module offers the projects module.

The ``projects`` module owns project lifecycle; it does not own the tasks filed
under a project (architecture doc section 5). These two functions are the tasks
module's public answer to "how much work is in these projects?" and "this project
is going away", so the projects service never reads or writes the tasks table
itself.

Neither function commits. Detaching runs inside the projects service's own
transaction --- with one activity event per task it changes --- so no database
state ever shows a task filed under a project that no longer exists, or a detach
the log does not mention (section 6.2).
"""

import uuid
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.modules.activity.enums import ActivityVerb
from app.modules.activity.recorder import ActivityRecorder
from app.modules.projects.models import Project
from app.modules.tasks import history, repository
from app.modules.users.models import User


@dataclass(frozen=True)
class ProjectTaskCounts:
    """How much work a project holds. ``open`` is everything not yet done."""

    total: int = 0
    open: int = 0


def count_by_project(
    session: Session, project_ids: Collection[uuid.UUID]
) -> Mapping[uuid.UUID, ProjectTaskCounts]:
    """Counts for each of ``project_ids``; a project with no tasks counts zero."""
    found = repository.count_by_project(session, project_ids)
    return {
        project_id: ProjectTaskCounts(*found.get(project_id, (0, 0)))
        for project_id in project_ids
    }


def detach_project(session: Session, *, project: Project, actor: User) -> Sequence[uuid.UUID]:
    """Take every task out of ``project``; return the tasks changed.

    The tasks stay in their workspace, under "no project", each as a recorded
    edit by ``actor`` with a new version and a ``task.updated`` event that still
    names the project as it was.
    """
    was = history.project_ref(project)
    detached = repository.detach_project(session, project_id=project.id, actor_id=actor.id)
    recorder = ActivityRecorder(session)
    for task in detached:
        recorder.record(
            ActivityVerb.TASK_UPDATED,
            workspace_id=task.workspace_id,
            actor=actor,
            task_id=task.id,
            task_title=task.title,
            task_version=task.version,
            changes={"project": {"from": was, "to": None}},
        )
    return [task.id for task in detached]
