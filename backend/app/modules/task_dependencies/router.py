"""HTTP routes for task dependencies.

Routes parse/validate input, call the application service, and serialize
output. No business rules live here (architecture doc section 4.1).

* ``/tasks/{task_id}/dependencies`` --- both directions of one task's
  dependencies (``GET``), and making it wait on another task of its workspace
  (``POST``, answering with both directions again, so a client redraws from one
  response). A task the caller cannot reach answers ``TASK_NOT_FOUND``.
* ``/tasks/{task_id}/dependencies/{blocking_task_id}`` --- ``DELETE``: the task
  no longer waits on that one.

A blocker from another workspace is ``422 DEPENDENCY_NOT_IN_WORKSPACE``, like a
missing one; a task on itself ``422 DEPENDENCY_ON_ITSELF``; a repeated link
``409 DEPENDENCY_EXISTS``; and a link that would close a loop ``409
DEPENDENCY_CYCLE``.
"""

import uuid

from fastapi import APIRouter, Response, status

from app.modules.auth.dependencies import CurrentUser
from app.modules.task_dependencies.dependencies import TaskDependencyServiceDep
from app.modules.task_dependencies.schemas import (
    DependencyCreate,
    DependencyTask,
    TaskDependenciesRead,
)
from app.modules.task_dependencies.service import TaskDependencies, TaskDependencyService
from app.modules.tasks.models import Task
from app.modules.users.models import User

router = APIRouter(tags=["task dependencies"])


def _read(
    service: TaskDependencyService, dependencies: TaskDependencies, actor: User
) -> TaskDependenciesRead:
    """Both directions, each task with what the caller may do to it."""
    capabilities = service.capabilities(dependencies, actor=actor)

    def one(task: Task) -> DependencyTask:
        return DependencyTask.model_validate(task).model_copy(
            update={"capabilities": capabilities.get(task.id, [])}
        )

    return TaskDependenciesRead(
        blocked_by=[one(task) for task in dependencies.blocked_by],
        blocking=[one(task) for task in dependencies.blocking],
    )


@router.get("/tasks/{task_id}/dependencies", response_model=TaskDependenciesRead)
def list_dependencies(
    task_id: uuid.UUID, user: CurrentUser, service: TaskDependencyServiceDep
) -> TaskDependenciesRead:
    """What the task waits on, and what waits on it."""
    return _read(service, service.dependencies_of(task_id, actor=user), user)


@router.post(
    "/tasks/{task_id}/dependencies",
    response_model=TaskDependenciesRead,
    status_code=status.HTTP_201_CREATED,
)
def add_dependency(
    task_id: uuid.UUID,
    payload: DependencyCreate,
    user: CurrentUser,
    service: TaskDependencyServiceDep,
) -> TaskDependenciesRead:
    """Make the task wait on another. Whoever may change the waiting task."""
    return _read(service, service.add_blocker(task_id, payload, actor=user), user)


@router.delete(
    "/tasks/{task_id}/dependencies/{blocking_task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_dependency(
    task_id: uuid.UUID,
    blocking_task_id: uuid.UUID,
    user: CurrentUser,
    service: TaskDependencyServiceDep,
) -> Response:
    """The task no longer waits on ``blocking_task_id``."""
    service.remove_blocker(task_id, blocking_task_id, actor=user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
