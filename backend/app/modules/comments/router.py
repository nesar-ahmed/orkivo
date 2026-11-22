"""HTTP routes for comments.

Routes parse/validate input, call the application service, and serialize
output. No business rules live here (architecture doc section 4.1).

* ``/tasks/{task_id}/comments`` --- a task's conversation: list (oldest first)
  and add. A task the caller cannot reach answers ``TASK_NOT_FOUND``.
* ``/comments/{comment_id}`` --- edit (its author) or delete (its author, or an
  owner or admin). A comment the caller cannot reach answers
  ``COMMENT_NOT_FOUND``; one they can see but not change, ``COMMENT_FORBIDDEN``.

Every comment in a response lists the members it mentions, so a client can show
``<@id>`` tokens as names.
"""

import uuid
from collections.abc import Mapping
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.modules.auth.dependencies import CurrentUser
from app.modules.comments.dependencies import CommentServiceDep
from app.modules.comments.mentions import mentioned_ids
from app.modules.comments.models import TaskComment
from app.modules.comments.schemas import (
    CommentCreate,
    CommentListResponse,
    CommentPerson,
    CommentRead,
    CommentUpdate,
)
from app.modules.users.models import User

router = APIRouter(tags=["comments"])


def _read(comment: TaskComment, people: Mapping[uuid.UUID, User]) -> CommentRead:
    """A comment plus the members it mentions, in the order the body names them."""
    base = CommentRead.model_validate(comment)
    mentions = [
        CommentPerson.model_validate(people[person_id])
        for person_id in mentioned_ids(comment.body)
        if person_id in people
    ]
    return base.model_copy(update={"mentions": mentions})

PageParam = Annotated[int, Query(ge=1)]
PageSizeParam = Annotated[int, Query(ge=1, le=100)]


@router.get("/tasks/{task_id}/comments", response_model=CommentListResponse)
def list_comments(
    task_id: uuid.UUID,
    user: CurrentUser,
    service: CommentServiceDep,
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
) -> CommentListResponse:
    """A task's conversation, oldest first."""
    items, total, pages = service.list_comments(
        task_id, actor=user, page=page, page_size=page_size
    )
    people = service.mentions_in(items)
    return CommentListResponse(
        items=[_read(comment, people) for comment in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post(
    "/tasks/{task_id}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
)
def add_comment(
    task_id: uuid.UUID, payload: CommentCreate, user: CurrentUser, service: CommentServiceDep
) -> CommentRead:
    """Comment on a task. Anyone but a viewer, while the workspace is active."""
    comment = service.add_comment(task_id, payload, actor=user)
    return _read(comment, service.mentions_in([comment]))


@router.patch("/comments/{comment_id}", response_model=CommentRead)
def edit_comment(
    comment_id: uuid.UUID,
    payload: CommentUpdate,
    user: CurrentUser,
    service: CommentServiceDep,
) -> CommentRead:
    """Change what you said. The author only."""
    comment = service.edit_comment(comment_id, payload, actor=user)
    return _read(comment, service.mentions_in([comment]))


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: uuid.UUID, user: CurrentUser, service: CommentServiceDep
) -> Response:
    """Remove a comment: its author, or an owner or admin."""
    service.delete_comment(comment_id, actor=user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
