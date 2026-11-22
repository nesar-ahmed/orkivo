"""HTTP route for search across the caller's workspaces.

Routes parse/validate input, call the application service, and serialize
output. No business rules live here (architecture doc section 4.1).

* ``GET /search?q=…`` --- workspaces, projects and tasks whose name contains ``q``,
  in every workspace the caller may read, up to ``limit`` of each (default 8).
  Nothing outside the caller's workspaces is ever searched, so a result --- or
  its absence --- says nothing about anyone else's.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.modules.auth.dependencies import CurrentUser
from app.modules.search.dependencies import SearchServiceDep
from app.modules.search.schemas import (
    SearchProjectHit,
    SearchProjectRef,
    SearchResponse,
    SearchTaskHit,
    SearchWorkspace,
)

router = APIRouter(tags=["search"])

#: The most of each kind one response may carry.
MAX_RESULTS_PER_KIND = 20


@router.get("/search", response_model=SearchResponse)
def search(
    user: CurrentUser,
    service: SearchServiceDep,
    q: Annotated[str, Query(min_length=1, max_length=200, description="What to look for.")],
    limit: Annotated[int, Query(ge=1, le=MAX_RESULTS_PER_KIND)] = 8,
) -> SearchResponse:
    """Find workspaces, projects and tasks by name, anywhere the caller may look."""
    results = service.search(q, actor=user, limit=limit)
    return SearchResponse(
        query=q.strip(),
        workspaces=[SearchWorkspace.model_validate(workspace) for workspace in results.workspaces],
        projects=[
            SearchProjectHit(
                id=project.id,
                name=project.name,
                workspace=SearchWorkspace.model_validate(workspace),
            )
            for project, workspace in results.projects
        ],
        tasks=[
            SearchTaskHit(
                id=task.id,
                title=task.title,
                status=task.status,
                priority=task.priority,
                due_date=task.due_date,
                project=SearchProjectRef.model_validate(task.project) if task.project else None,
                workspace=SearchWorkspace.model_validate(workspace),
            )
            for task, workspace in results.tasks
        ],
    )
