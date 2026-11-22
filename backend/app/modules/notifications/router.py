"""HTTP routes for the inbox and for watching tasks.

Routes parse/validate input, call the application service, and serialize
output. No business rules live here (architecture doc section 4.1).

* ``/notifications`` --- the caller's inbox (newest first), its unread count,
  and marking read. Another person's notification answers
  ``NOTIFICATION_NOT_FOUND``. ``/notifications/read-all`` and
  ``/notifications/unread-count`` are declared before ``/{notification_id}`` so
  the literal paths win.
* ``/tasks/{task_id}/watchers`` --- who follows a task; ``POST`` to follow it
  yourself, ``DELETE`` to stop. A task the caller cannot reach answers
  ``TASK_NOT_FOUND``.

There is no route that creates a notification: they are written by the task and
comment use cases, in the transaction that makes the change.
"""

import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from app.modules.auth.dependencies import CurrentUser
from app.modules.notifications.dependencies import NotificationServiceDep
from app.modules.notifications.schemas import (
    NotificationListResponse,
    NotificationPerson,
    NotificationRead,
    NotificationTask,
    NotificationWorkspace,
    UnreadCountRead,
    WatchersRead,
)
from app.modules.users.models import User

router = APIRouter(tags=["notifications"])

PageParam = Annotated[int, Query(ge=1)]
PageSizeParam = Annotated[int, Query(ge=1, le=100)]
NotificationId = Annotated[uuid.UUID, Path(description="One of the caller's notifications.")]


def _watchers(people: Sequence[User], watching: bool) -> WatchersRead:
    return WatchersRead(
        items=[NotificationPerson.model_validate(person) for person in people],
        watching=watching,
    )


# --- the inbox ---------------------------------------------------------------
@router.get("/notifications", response_model=NotificationListResponse)
def list_notifications(
    user: CurrentUser,
    service: NotificationServiceDep,
    unread: Annotated[bool, Query(description="Only notifications not yet read.")] = False,
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
) -> NotificationListResponse:
    """The caller's inbox, newest first."""
    rows, total, pages, unread_count = service.inbox(
        actor=user, unread_only=unread, page=page, page_size=page_size
    )
    return NotificationListResponse(
        items=[
            NotificationRead(
                id=item.id,
                kind=item.kind,
                actor=NotificationPerson.model_validate(item.actor) if item.actor else None,
                task=NotificationTask.model_validate(item.task),
                workspace=NotificationWorkspace.model_validate(item.workspace),
                comment_id=item.comment_id,
                excerpt=excerpt,
                read_at=item.read_at,
                created_at=item.created_at,
            )
            for item, excerpt in rows
        ],
        total=total,
        unread=unread_count,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/notifications/unread-count", response_model=UnreadCountRead)
def unread_count(user: CurrentUser, service: NotificationServiceDep) -> UnreadCountRead:
    """How many notifications the caller has not read. Cheap enough to poll."""
    return UnreadCountRead(count=service.unread_count(actor=user))


@router.post(
    "/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
def mark_all_read(user: CurrentUser, service: NotificationServiceDep) -> Response:
    service.mark_all_read(actor=user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/notifications/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def mark_read(
    notification_id: NotificationId, user: CurrentUser, service: NotificationServiceDep
) -> Response:
    service.mark_read(notification_id, actor=user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- watching a task ---------------------------------------------------------
@router.get("/tasks/{task_id}/watchers", response_model=WatchersRead)
def list_watchers(
    task_id: uuid.UUID, user: CurrentUser, service: NotificationServiceDep
) -> WatchersRead:
    """Who follows the task, and whether the caller does."""
    return _watchers(*service.watchers(task_id, actor=user))


@router.post("/tasks/{task_id}/watchers", response_model=WatchersRead)
def watch_task(
    task_id: uuid.UUID, user: CurrentUser, service: NotificationServiceDep
) -> WatchersRead:
    """Follow a task: hear about its comments. Already following is fine."""
    return _watchers(*service.watch(task_id, actor=user))


@router.delete(
    "/tasks/{task_id}/watchers", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
def unwatch_task(
    task_id: uuid.UUID, user: CurrentUser, service: NotificationServiceDep
) -> Response:
    """Stop following a task. Not following is fine."""
    service.unwatch(task_id, actor=user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
