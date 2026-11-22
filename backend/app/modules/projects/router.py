"""HTTP routes for projects.

Routes parse/validate input, call the application service, and serialize
output. No business rules live here (architecture doc section 4.1).

Two shapes, like tasks:

* ``/workspaces/{workspace_id}/projects`` --- one tenant's projects: list (with
  task counts) and create. Outsiders get ``WORKSPACE_NOT_FOUND``.
* ``/projects/{project_id}`` --- one project, wherever it lives. A project the
  caller cannot reach answers ``PROJECT_NOT_FOUND``, exactly like one that does
  not exist. ``PATCH`` and ``DELETE`` accept the ``version`` the client read and
  answer ``409 PROJECT_CONFLICT`` if a colleague changed the project since.

Deleting a project keeps its tasks: they stay in the workspace, without a project.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from app.modules.auth.dependencies import CurrentUser
from app.modules.projects.dependencies import ProjectServiceDep
from app.modules.projects.schemas import (
    ProjectCreate,
    ProjectListResponse,
    ProjectRead,
    ProjectSummaryRead,
    ProjectUpdate,
)

router = APIRouter(tags=["projects"])

WorkspaceId = Annotated[uuid.UUID, Path(description="Workspace holding the projects.")]
PageParam = Annotated[int, Query(ge=1)]
PageSizeParam = Annotated[int, Query(ge=1, le=100)]


# --- one workspace's projects ----------------------------------------------
@router.get("/workspaces/{workspace_id}/projects", response_model=ProjectListResponse)
def list_projects(
    workspace_id: WorkspaceId,
    user: CurrentUser,
    service: ProjectServiceDep,
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
) -> ProjectListResponse:
    """A workspace's projects, alphabetically, each with its task counts."""
    rows, total, pages = service.list_projects(
        workspace_id, actor=user, page=page, page_size=page_size
    )
    return ProjectListResponse(
        items=[
            ProjectSummaryRead(
                **ProjectRead.model_validate(project).model_dump(),
                task_count=counts.total,
                open_task_count=counts.open,
            )
            for project, counts in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post(
    "/workspaces/{workspace_id}/projects",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    workspace_id: WorkspaceId,
    payload: ProjectCreate,
    user: CurrentUser,
    service: ProjectServiceDep,
) -> ProjectRead:
    """Add a project to a workspace. Owners, admins and managers, while it is active."""
    return ProjectRead.model_validate(service.create_project(workspace_id, payload, actor=user))


# --- one project -------------------------------------------------------------
@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: uuid.UUID, user: CurrentUser, service: ProjectServiceDep
) -> ProjectRead:
    return ProjectRead.model_validate(service.get_project(project_id, actor=user))


@router.patch("/projects/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    user: CurrentUser,
    service: ProjectServiceDep,
) -> ProjectRead:
    """Rename or describe a project. Owners, admins and managers, while it is active."""
    return ProjectRead.model_validate(service.update_project(project_id, payload, actor=user))


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID,
    user: CurrentUser,
    service: ProjectServiceDep,
    version: Annotated[
        int | None,
        Query(ge=1, description="Delete only if the project is still at this version."),
    ] = None,
) -> Response:
    """Delete a project; its tasks stay, without a project. Owners and admins."""
    service.delete_project(project_id, actor=user, version=version)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
