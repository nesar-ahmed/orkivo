"""HTTP routes for the activity log. Read-only by design.

* ``/tasks/{task_id}/activity`` --- one task's history, for anyone who may read
  the task; everyone else gets ``TASK_NOT_FOUND``.
* ``/workspaces/{workspace_id}/activity`` --- the workspace's feed, including the
  history of tasks that have since been deleted.

There is no POST, PATCH or DELETE: events are written by the task and comment
use cases, in the transaction that makes the change (architecture doc 4.1).
"""

import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.modules.activity.dependencies import ActivityServiceDep
from app.modules.activity.models import ActivityEvent
from app.modules.activity.schemas import ActivityListResponse, ActivityRead
from app.modules.auth.dependencies import CurrentUser

router = APIRouter(tags=["activity"])

PageParam = Annotated[int, Query(ge=1)]
PageSizeParam = Annotated[int, Query(ge=1, le=100)]


def _page(
    items: Sequence[ActivityEvent], total: int, pages: int, page: int, page_size: int
) -> ActivityListResponse:
    return ActivityListResponse(
        items=[ActivityRead.model_validate(event) for event in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/tasks/{task_id}/activity", response_model=ActivityListResponse)
def task_history(
    task_id: uuid.UUID,
    user: CurrentUser,
    service: ActivityServiceDep,
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
) -> ActivityListResponse:
    """What happened to one task, newest first."""
    items, total, pages = service.task_history(
        task_id, actor=user, page=page, page_size=page_size
    )
    return _page(items, total, pages, page, page_size)


@router.get("/workspaces/{workspace_id}/activity", response_model=ActivityListResponse)
def workspace_feed(
    workspace_id: Annotated[uuid.UUID, Path(description="Workspace whose feed to read.")],
    user: CurrentUser,
    service: ActivityServiceDep,
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
) -> ActivityListResponse:
    """Everything that happened in a workspace, newest first."""
    items, total, pages = service.workspace_feed(
        workspace_id, actor=user, page=page, page_size=page_size
    )
    return _page(items, total, pages, page, page_size)
