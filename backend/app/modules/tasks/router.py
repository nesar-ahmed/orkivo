"""HTTP routes for tasks.

Routes parse/validate input, call the application service, and serialize
output. No business rules live here (architecture doc section 4.1).

Every route requires a live session and hands the authenticated user to the
service as the *actor*. The caller never supplies an owner or a role, and a
workspace id in the path is only a request: membership is resolved from the
database by the access policy (architecture doc section 9).

Three shapes:

* ``/workspaces/{workspace_id}/tasks`` --- one tenant's board: list and create.
  Any member may use it; outsiders get ``WORKSPACE_NOT_FOUND``.
* ``/tasks/{task_id}`` --- one task, wherever it lives. Task ids are globally
  unique, so a link keeps working if the company is renamed. A task the caller
  cannot reach answers ``TASK_NOT_FOUND``, exactly like one that does not exist.
  ``PATCH`` and ``DELETE`` accept the ``version`` the client read and answer
  ``409 TASK_CONFLICT`` if a colleague changed the task since.
* ``/tasks`` --- list and create in the caller's *personal* workspace. Kept so
  clients written before tasks were shared keep working unchanged.
"""

import math
import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from app.modules.auth.dependencies import CurrentUser
from app.modules.tasks.dependencies import TaskServiceDep
from app.modules.tasks.enums import TaskPriority, TaskStatus
from app.modules.tasks.models import Task
from app.modules.tasks.schemas import (
    TaskCreate,
    TaskListResponse,
    TaskRead,
    TaskUpdate,
)

router = APIRouter(tags=["tasks"])

WorkspaceId = Annotated[uuid.UUID, Path(description="Workspace holding the tasks.")]
StatusFilter = Annotated[TaskStatus | None, Query(alias="status")]
SearchParam = Annotated[str | None, Query(min_length=1, max_length=200)]
PageParam = Annotated[int, Query(ge=1)]
PageSizeParam = Annotated[int, Query(ge=1, le=100)]


def _page(items: Sequence[Task], total: int, page: int, page_size: int) -> TaskListResponse:
    return TaskListResponse(
        items=[TaskRead.model_validate(task) for task in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


# --- one workspace's board -------------------------------------------------
@router.get("/workspaces/{workspace_id}/tasks", response_model=TaskListResponse)
def list_workspace_tasks(
    workspace_id: WorkspaceId,
    user: CurrentUser,
    service: TaskServiceDep,
    status_filter: StatusFilter = None,
    priority: TaskPriority | None = None,
    search: SearchParam = None,
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
) -> TaskListResponse:
    """A workspace's tasks, for its members, with pagination and filters."""
    items, total = service.list_tasks(
        workspace_id,
        actor=user,
        status=status_filter,
        priority=priority,
        search=search,
        page=page,
        page_size=page_size,
    )
    return _page(items, total, page, page_size)


@router.post(
    "/workspaces/{workspace_id}/tasks",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
)
def create_workspace_task(
    workspace_id: WorkspaceId, payload: TaskCreate, user: CurrentUser, service: TaskServiceDep
) -> TaskRead:
    """Add a task to a workspace. Any member, while the workspace is active."""
    return TaskRead.model_validate(service.create_task(workspace_id, payload, actor=user))


# --- the caller's personal workspace ---------------------------------------
@router.get("/tasks", response_model=TaskListResponse)
def list_tasks(
    user: CurrentUser,
    service: TaskServiceDep,
    status_filter: StatusFilter = None,
    priority: TaskPriority | None = None,
    search: SearchParam = None,
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
) -> TaskListResponse:
    """The caller's private tasks with pagination and optional filters."""
    items, total = service.list_tasks(
        service.personal_workspace_id(actor=user),
        actor=user,
        status=status_filter,
        priority=priority,
        search=search,
        page=page,
        page_size=page_size,
    )
    return _page(items, total, page, page_size)


@router.post("/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, user: CurrentUser, service: TaskServiceDep) -> TaskRead:
    """Add a private task to the caller's personal workspace."""
    workspace_id = service.personal_workspace_id(actor=user)
    return TaskRead.model_validate(service.create_task(workspace_id, payload, actor=user))


# --- one task --------------------------------------------------------------
@router.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(task_id: uuid.UUID, user: CurrentUser, service: TaskServiceDep) -> TaskRead:
    return TaskRead.model_validate(service.get_task(task_id, actor=user))


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(
    task_id: uuid.UUID, payload: TaskUpdate, user: CurrentUser, service: TaskServiceDep
) -> TaskRead:
    return TaskRead.model_validate(service.update_task(task_id, payload, actor=user))


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: uuid.UUID,
    user: CurrentUser,
    service: TaskServiceDep,
    version: Annotated[
        int | None,
        Query(ge=1, description="Delete only if the task is still at this version."),
    ] = None,
) -> Response:
    service.delete_task(task_id, actor=user, version=version)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
