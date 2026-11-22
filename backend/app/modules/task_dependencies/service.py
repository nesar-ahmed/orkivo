"""Application service implementing task dependency use cases.

Business rules live here, not in route handlers. Transaction boundaries are
committed at this use-case layer and rolled back on failure (architecture doc
section 6.2).

A dependency inherits its task's access rule, through the same code path as a
comment (``TaskService.authorized_task``):

==============================  ================  ===============================
Use case                        Action            On the task
==============================  ================  ===============================
Read a task's dependencies      ``read``          the task in the path
Add or remove a blocker         task ``edit``     the task that waits
==============================  ================  ===============================

What a task waits on is part of planning *that* task, so changing it takes
exactly the right to change the task (``TaskService.changeable_task``): anyone
running the work, or a member for a task they created or hold. The blocking task
only has to be readable in the same workspace. So a suspended company's plans
stay readable and frozen, and a task the caller cannot see reads as not found.

Four rules keep the links meaningful, each checked before anything is written:
the blocking task is in the same workspace (one ``422`` for "elsewhere" and
"missing"), a task never waits on itself, the same link is never made twice, and
no link closes a loop --- a task cannot wait on something that already waits on
it, however indirectly. A task waits on at most ``MAX_BLOCKERS_PER_TASK``
others.

Adding or removing a blocker is recorded on the *waiting* task's history in the
same transaction. It is not a change to the task itself, so its version does not
move and nobody editing it meanwhile is refused.
"""

import uuid
from collections.abc import Mapping
from typing import NamedTuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.activity.enums import ActivityVerb
from app.modules.activity.recorder import ActivityRecorder
from app.modules.task_dependencies import repository
from app.modules.task_dependencies.exceptions import (
    DependencyCycleError,
    DependencyExistsError,
    DependencyLimitReachedError,
    DependencyNotFoundError,
    DependencyNotInWorkspaceError,
    SelfDependencyError,
)
from app.modules.task_dependencies.models import TaskDependency
from app.modules.task_dependencies.schemas import DependencyCreate
from app.modules.tasks.enums import TaskAction
from app.modules.tasks.models import Task
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from app.modules.workspaces.enums import WorkspaceAction

#: Enough for any real plan; few enough that the task page can list them all.
MAX_BLOCKERS_PER_TASK = 50


class TaskDependencies(NamedTuple):
    """One task's dependencies, both ways, open work first."""

    blocked_by: list[Task]
    blocking: list[Task]


class TaskDependencyService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._tasks = TaskService(session)
        self._recorder = ActivityRecorder(session)

    def dependencies_of(self, task_id: uuid.UUID, *, actor: User) -> TaskDependencies:
        task = self._tasks.authorized_task(task_id, actor=actor, action=WorkspaceAction.READ)
        return self._both_ways(task)

    def add_blocker(
        self, task_id: uuid.UUID, data: DependencyCreate, *, actor: User
    ) -> TaskDependencies:
        """Make the task wait on another task of its workspace."""
        task = self._tasks.changeable_task(task_id, actor=actor, action=TaskAction.EDIT)
        if data.blocking_task_id == task.id:
            raise SelfDependencyError
        blocker = repository.task_in_workspace(
            self._session, task.workspace_id, data.blocking_task_id
        )
        if blocker is None:
            raise DependencyNotInWorkspaceError(data.blocking_task_id)
        repository.lock_workspace(self._session, task.workspace_id)
        if repository.get_link(
            self._session,
            workspace_id=task.workspace_id,
            blocked_id=task.id,
            blocking_id=blocker.id,
        ):
            raise DependencyExistsError
        if repository.count_blockers(self._session, task.id) >= MAX_BLOCKERS_PER_TASK:
            raise DependencyLimitReachedError(MAX_BLOCKERS_PER_TASK)
        if repository.reaches(
            self._session, workspace_id=task.workspace_id, start=task.id, target=blocker.id
        ):
            raise DependencyCycleError
        link = TaskDependency(
            workspace_id=task.workspace_id,
            blocked_task_id=task.id,
            blocking_task_id=blocker.id,
            created_by=actor,
        )
        try:
            repository.add_link(self._session, link)
        except IntegrityError:
            # Someone made the same link between the check and the insert.
            self._session.rollback()
            raise DependencyExistsError from None
        self._record(ActivityVerb.DEPENDENCY_ADDED, task, blocker, actor=actor)
        return self._both_ways(task)

    def remove_blocker(
        self, task_id: uuid.UUID, blocking_task_id: uuid.UUID, *, actor: User
    ) -> None:
        """The task no longer waits on ``blocking_task_id``."""
        task = self._tasks.changeable_task(task_id, actor=actor, action=TaskAction.EDIT)
        link = repository.get_link(
            self._session,
            workspace_id=task.workspace_id,
            blocked_id=task.id,
            blocking_id=blocking_task_id,
        )
        blocker = repository.task_in_workspace(self._session, task.workspace_id, blocking_task_id)
        if link is None or blocker is None:
            raise DependencyNotFoundError
        repository.delete_link(self._session, link)
        self._session.flush()
        self._record(ActivityVerb.DEPENDENCY_REMOVED, task, blocker, actor=actor)

    # --- helpers -----------------------------------------------------------
    def capabilities(
        self, dependencies: TaskDependencies, *, actor: User
    ) -> Mapping[uuid.UUID, list[TaskAction]]:
        """What the caller may do to each task on either side, for the response.

        The same answer every task response carries (``TaskService.task_capabilities``),
        so "may I unlink this?" is decided by the rule that refuses the request.
        """
        return self._tasks.task_capabilities(
            [*dependencies.blocked_by, *dependencies.blocking], actor=actor
        )

    def _both_ways(self, task: Task) -> TaskDependencies:
        return TaskDependencies(
            blocked_by=list(
                repository.blockers_of(
                    self._session, workspace_id=task.workspace_id, task_id=task.id
                )
            ),
            blocking=list(
                repository.blocked_by(
                    self._session, workspace_id=task.workspace_id, task_id=task.id
                )
            ),
        )

    def _record(self, verb: ActivityVerb, task: Task, blocker: Task, *, actor: User) -> None:
        """The event on the waiting task's history, then the commit, as one step."""
        ref = {"id": str(blocker.id), "name": blocker.title}
        change = (
            {"from": None, "to": ref}
            if verb is ActivityVerb.DEPENDENCY_ADDED
            else {"from": ref, "to": None}
        )
        try:
            self._recorder.record(
                verb,
                workspace_id=task.workspace_id,
                actor=actor,
                task_id=task.id,
                task_title=task.title,
                task_version=task.version,
                changes={"blocked_by": change},
            )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
