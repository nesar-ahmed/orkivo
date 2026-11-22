"""HTTP routes for labels.

Routes parse/validate input, call the application service, and serialize
output. No business rules live here (architecture doc section 4.1).

Two shapes, like projects:

* ``/workspaces/{workspace_id}/labels`` --- one tenant's labels: list (with task
  counts) and create. Outsiders get ``WORKSPACE_NOT_FOUND``.
* ``/labels/{label_id}`` --- one label, wherever it lives. A label the caller
  cannot reach answers ``LABEL_NOT_FOUND``, exactly like one that does not
  exist. ``PATCH`` and ``DELETE`` accept the ``version`` the client read and
  answer ``409 LABEL_CONFLICT`` if a colleague changed the label since.

Deleting a label keeps its tasks: it is only taken off them.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from app.modules.auth.dependencies import CurrentUser
from app.modules.labels.dependencies import LabelServiceDep
from app.modules.labels.schemas import (
    LabelCreate,
    LabelListResponse,
    LabelRead,
    LabelSummaryRead,
    LabelUpdate,
)

router = APIRouter(tags=["labels"])

WorkspaceId = Annotated[uuid.UUID, Path(description="Workspace holding the labels.")]
PageParam = Annotated[int, Query(ge=1)]
PageSizeParam = Annotated[int, Query(ge=1, le=100)]


# --- one workspace's labels --------------------------------------------------
@router.get("/workspaces/{workspace_id}/labels", response_model=LabelListResponse)
def list_labels(
    workspace_id: WorkspaceId,
    user: CurrentUser,
    service: LabelServiceDep,
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
) -> LabelListResponse:
    """A workspace's labels, alphabetically, each with how many tasks carry it."""
    rows, total, pages = service.list_labels(
        workspace_id, actor=user, page=page, page_size=page_size
    )
    return LabelListResponse(
        items=[
            LabelSummaryRead(**LabelRead.model_validate(label).model_dump(), task_count=count)
            for label, count in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post(
    "/workspaces/{workspace_id}/labels",
    response_model=LabelRead,
    status_code=status.HTTP_201_CREATED,
)
def create_label(
    workspace_id: WorkspaceId,
    payload: LabelCreate,
    user: CurrentUser,
    service: LabelServiceDep,
) -> LabelRead:
    """Add a label to a workspace. Owners, admins and managers, while it is active."""
    return LabelRead.model_validate(service.create_label(workspace_id, payload, actor=user))


# --- one label ---------------------------------------------------------------
@router.get("/labels/{label_id}", response_model=LabelRead)
def get_label(label_id: uuid.UUID, user: CurrentUser, service: LabelServiceDep) -> LabelRead:
    return LabelRead.model_validate(service.get_label(label_id, actor=user))


@router.patch("/labels/{label_id}", response_model=LabelRead)
def update_label(
    label_id: uuid.UUID,
    payload: LabelUpdate,
    user: CurrentUser,
    service: LabelServiceDep,
) -> LabelRead:
    """Rename or recolor a label. Owners, admins and managers, while it is active."""
    return LabelRead.model_validate(service.update_label(label_id, payload, actor=user))


@router.delete("/labels/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_label(
    label_id: uuid.UUID,
    user: CurrentUser,
    service: LabelServiceDep,
    version: Annotated[
        int | None,
        Query(ge=1, description="Delete only if the label is still at this version."),
    ] = None,
) -> Response:
    """Delete a label; it is taken off every task that carries it. Owners and admins."""
    service.delete_label(label_id, actor=user, version=version)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
