"""HTTP routes for tasks.

Routes parse/validate input, call the application service, and serialize
output. No business rules live here (architecture doc section 4.1).

Every route requires a live session and passes the authenticated user's id down
as the ownership scope. The caller cannot supply an owner: user-supplied owner,
workspace or role values are never trusted (architecture doc section 9).
"""

import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.modules.auth.dependencies import CurrentUser
from app.modules.tasks.dependencies import TaskServiceDep
from app.modules.tasks.enums import TaskPriority, TaskStatus
from app.modules.tasks.schemas import (
    TaskCreate,
    TaskListResponse,
    TaskRead,
    TaskUpdate,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=TaskListResponse)
def list_tasks(
    user: CurrentUser,
    service: TaskServiceDep,
    status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None,
    priority: TaskPriority | None = None,
    search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TaskListResponse:
    """List the caller's tasks with pagination and optional filters."""
    items, total = service.list_tasks(
        owner_id=user.id,
        status=status_filter,
        priority=priority,
        search=search,
        page=page,
        page_size=page_size,
    )
    return TaskListResponse(
        items=[TaskRead.model_validate(task) for task in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, user: CurrentUser, service: TaskServiceDep) -> TaskRead:
    task = service.create_task(payload, owner_id=user.id)
    return TaskRead.model_validate(task)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: uuid.UUID, user: CurrentUser, service: TaskServiceDep) -> TaskRead:
    return TaskRead.model_validate(service.get_task(task_id, owner_id=user.id))


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(
    task_id: uuid.UUID, payload: TaskUpdate, user: CurrentUser, service: TaskServiceDep
) -> TaskRead:
    return TaskRead.model_validate(service.update_task(task_id, payload, owner_id=user.id))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: uuid.UUID, user: CurrentUser, service: TaskServiceDep) -> Response:
    service.delete_task(task_id, owner_id=user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
