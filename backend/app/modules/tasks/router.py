"""HTTP routes for tasks.

Routes parse/validate input, call the application service, and serialize
output. No business rules live here (architecture doc section 4.1).

Every route requires a live session and hands the authenticated user to the
service as the *actor*. The caller never supplies an owner or a role, and a
workspace id in the path is only a request: membership is resolved from the
database by the access policy (architecture doc section 9).

Three shapes:

* ``/workspaces/{workspace_id}/tasks`` --- one tenant's board: list and create.
  Any member may list it and anyone but a viewer may add to it; outsiders get
  ``WORKSPACE_NOT_FOUND``. ``.../tasks/bulk-update`` and ``.../tasks/bulk-delete``
  change or delete up to a page of its tasks at once, all or nothing; a refusal
  lists every task that caused it in ``details`` (``tasks.<index>.<field>``).
* ``/tasks/{task_id}`` --- one task, wherever it lives. Task ids are globally
  unique, so a link keeps working if the company is renamed. A task the caller
  cannot reach answers ``TASK_NOT_FOUND``, exactly like one that does not exist.
  ``PATCH`` and ``DELETE`` accept the ``version`` the client read and answer
  ``409 TASK_CONFLICT`` if a colleague changed the task since.
* ``/tasks`` --- list and create in the caller's *personal* workspace. Kept so
  clients written before tasks were shared keep working unchanged.
* ``/me/tasks`` --- the caller's own work across every workspace they are in:
  what is assigned to them, plus their private workspace's unassigned tasks.
  Sorted by due date unless asked otherwise, and filterable to one workspace.
  Not under ``/tasks``, where the next path segment is a task id.

Every task returned lists what the caller may do to it (``capabilities``:
``edit``, ``delete``). Changing or deleting another person's task takes a manager,
admin or owner; a member asking answers ``403 TASK_FORBIDDEN``.

The workspace list routes filter by ``?status=`` (one status, or ``open`` for
everything not done), ``?assignee=`` (a member's id, ``me`` or ``none``),
``?project=`` (a project's id or ``none``), ``?label=`` (a label's id or
``none``) and the due date (``?due_from=`` and ``?due_to=``, inclusive, and
``?has_due_date=``), and sort by ``?order=`` (``newest``; ``project``, which
keeps each project's tasks together for a grouped view; ``due``; or
``priority``). ``/me/tasks`` takes the same filters except ``assignee``, plus
``?workspace=``.
"""

import math
import uuid
from collections.abc import Sequence
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status
from fastapi.exceptions import RequestValidationError

from app.modules.auth.dependencies import CurrentUser
from app.modules.tasks.dependencies import TaskServiceDep
from app.modules.tasks.enums import (
    AssigneeScope,
    LabelScope,
    ProjectScope,
    StatusScope,
    TaskOrder,
    TaskPriority,
    TaskStatus,
)
from app.modules.tasks.models import Task
from app.modules.tasks.schemas import (
    BulkTaskDelete,
    BulkTaskUpdate,
    BulkTaskUpdateResponse,
    TaskCreate,
    TaskListResponse,
    TaskRead,
    TaskUpdate,
)
from app.modules.tasks.service import TaskService
from app.modules.users.models import User

router = APIRouter(tags=["tasks"])

WorkspaceId = Annotated[uuid.UUID, Path(description="Workspace holding the tasks.")]
StatusFilter = Annotated[
    TaskStatus | StatusScope | None,
    Query(alias="status", description="One status, or `open` for everything not done."),
]
AssigneeFilter = Annotated[
    uuid.UUID | AssigneeScope | None,
    Query(description="A member's id, `me` for the caller, or `none` for unassigned tasks."),
]
ProjectFilter = Annotated[
    uuid.UUID | ProjectScope | None,
    Query(description="A project's id, or `none` for tasks outside every project."),
]
LabelFilter = Annotated[
    uuid.UUID | LabelScope | None,
    Query(description="A label's id, or `none` for tasks carrying no label."),
]
DueFrom = Annotated[date | None, Query(description="Due on or after this date.")]
DueTo = Annotated[date | None, Query(description="Due on or before this date.")]
HasDueDate = Annotated[
    bool | None,
    Query(description="`true` for tasks with a due date, `false` for tasks without one."),
]
SearchParam = Annotated[str | None, Query(min_length=1, max_length=200)]
PageParam = Annotated[int, Query(ge=1)]
PageSizeParam = Annotated[int, Query(ge=1, le=100)]


def _check_due_window(due_from: date | None, due_to: date | None) -> None:
    """A window that ends before it starts is a malformed request, named on its end.

    Raised as the framework's own validation error, so it answers in the same
    ``422 VALIDATION_ERROR`` shape, with a field, as any other bad parameter.
    """
    if due_from is not None and due_to is not None and due_from > due_to:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("query", "due_to"),
                    "msg": "due_to must be on or after due_from.",
                    "input": due_to.isoformat(),
                }
            ]
        )


def _reads(service: TaskService, tasks: Sequence[Task], actor: User) -> list[TaskRead]:
    """Tasks as the API shows them: each with how many open tasks it still waits on,
    and what the caller may do to it. Two grouped reads per response, not per task."""
    open_blockers = service.open_blocker_counts(tasks)
    capabilities = service.task_capabilities(tasks, actor=actor)
    return [
        TaskRead.model_validate(task).model_copy(
            update={
                "open_blocker_count": open_blockers.get(task.id, 0),
                "capabilities": capabilities.get(task.id, []),
            }
        )
        for task in tasks
    ]


def _read(service: TaskService, task: Task, actor: User) -> TaskRead:
    return _reads(service, [task], actor)[0]


def _page(
    items: list[TaskRead],
    total: int,
    page: int,
    page_size: int,
) -> TaskListResponse:
    return TaskListResponse(
        items=items,
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
    assignee: AssigneeFilter = None,
    project: ProjectFilter = None,
    label: LabelFilter = None,
    due_from: DueFrom = None,
    due_to: DueTo = None,
    has_due_date: HasDueDate = None,
    search: SearchParam = None,
    order: TaskOrder = TaskOrder.NEWEST,
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
) -> TaskListResponse:
    """A workspace's tasks, for its members, with pagination and filters."""
    _check_due_window(due_from, due_to)
    items, total = service.list_tasks(
        workspace_id,
        actor=user,
        status=status_filter,
        priority=priority,
        assignee=assignee,
        project=project,
        label=label,
        due_from=due_from,
        due_to=due_to,
        has_due_date=has_due_date,
        search=search,
        order=order,
        page=page,
        page_size=page_size,
    )
    return _page(_reads(service, items, user), total, page, page_size)


@router.post(
    "/workspaces/{workspace_id}/tasks",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
)
def create_workspace_task(
    workspace_id: WorkspaceId, payload: TaskCreate, user: CurrentUser, service: TaskServiceDep
) -> TaskRead:
    """Add a task to a workspace. Anyone but a viewer, while the workspace is active."""
    task = service.create_task(workspace_id, payload, actor=user)
    return _read(service, task, user)


@router.post(
    "/workspaces/{workspace_id}/tasks/bulk-update", response_model=BulkTaskUpdateResponse
)
def bulk_update_tasks(
    workspace_id: WorkspaceId, payload: BulkTaskUpdate, user: CurrentUser, service: TaskServiceDep
) -> BulkTaskUpdateResponse:
    """Apply one set of changes to up to 100 of the workspace's tasks, all or nothing.

    Each task is held to the same rule as a single save: any task for a manager,
    admin or owner; for a member, only ones they created or are assigned to.
    """
    tasks = service.bulk_update(workspace_id, payload, actor=user)
    return BulkTaskUpdateResponse(items=_reads(service, tasks, user))


@router.post(
    "/workspaces/{workspace_id}/tasks/bulk-delete",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def bulk_delete_tasks(
    workspace_id: WorkspaceId, payload: BulkTaskDelete, user: CurrentUser, service: TaskServiceDep
) -> Response:
    """Delete up to 100 of the workspace's tasks, all or nothing.

    Any task for a manager, admin or owner; for a member, only ones they created.
    """
    service.bulk_delete(workspace_id, payload, actor=user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- the caller's personal workspace ---------------------------------------
@router.get("/tasks", response_model=TaskListResponse)
def list_tasks(
    user: CurrentUser,
    service: TaskServiceDep,
    status_filter: StatusFilter = None,
    priority: TaskPriority | None = None,
    assignee: AssigneeFilter = None,
    project: ProjectFilter = None,
    label: LabelFilter = None,
    due_from: DueFrom = None,
    due_to: DueTo = None,
    has_due_date: HasDueDate = None,
    search: SearchParam = None,
    order: TaskOrder = TaskOrder.NEWEST,
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
) -> TaskListResponse:
    """The caller's private tasks with pagination and optional filters."""
    _check_due_window(due_from, due_to)
    items, total = service.list_tasks(
        service.personal_workspace_id(actor=user),
        actor=user,
        status=status_filter,
        priority=priority,
        assignee=assignee,
        project=project,
        label=label,
        due_from=due_from,
        due_to=due_to,
        has_due_date=has_due_date,
        search=search,
        order=order,
        page=page,
        page_size=page_size,
    )
    return _page(_reads(service, items, user), total, page, page_size)


@router.post("/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, user: CurrentUser, service: TaskServiceDep) -> TaskRead:
    """Add a private task to the caller's personal workspace."""
    workspace_id = service.personal_workspace_id(actor=user)
    task = service.create_task(workspace_id, payload, actor=user)
    return _read(service, task, user)


# --- the caller's own work, everywhere ---------------------------------------
@router.get("/me/tasks", response_model=TaskListResponse)
def list_my_tasks(
    user: CurrentUser,
    service: TaskServiceDep,
    workspace: Annotated[
        uuid.UUID | None,
        Query(description="Only this workspace's tasks. One you are not in matches nothing."),
    ] = None,
    status_filter: StatusFilter = None,
    priority: TaskPriority | None = None,
    project: ProjectFilter = None,
    label: LabelFilter = None,
    due_from: DueFrom = None,
    due_to: DueTo = None,
    has_due_date: HasDueDate = None,
    search: SearchParam = None,
    order: TaskOrder = TaskOrder.DUE,
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
) -> TaskListResponse:
    """Everything assigned to the caller in any workspace, plus their private to-dos.

    Soonest due first by default. Each task carries its ``workspace_id``, so a
    client can say where it lives and link to it there.
    """
    _check_due_window(due_from, due_to)
    items, total = service.list_my_tasks(
        actor=user,
        workspace=workspace,
        status=status_filter,
        priority=priority,
        project=project,
        label=label,
        due_from=due_from,
        due_to=due_to,
        has_due_date=has_due_date,
        search=search,
        order=order,
        page=page,
        page_size=page_size,
    )
    return _page(_reads(service, items, user), total, page, page_size)


# --- one task --------------------------------------------------------------
@router.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(task_id: uuid.UUID, user: CurrentUser, service: TaskServiceDep) -> TaskRead:
    task = service.get_task(task_id, actor=user)
    return _read(service, task, user)


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(
    task_id: uuid.UUID, payload: TaskUpdate, user: CurrentUser, service: TaskServiceDep
) -> TaskRead:
    """Change a task: any task for a manager, admin or owner; for a member, one
    they created or are assigned to."""
    task = service.update_task(task_id, payload, actor=user)
    return _read(service, task, user)


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
    """Delete a task: any task for a manager, admin or owner; for a member, one
    they created."""
    service.delete_task(task_id, actor=user, version=version)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
