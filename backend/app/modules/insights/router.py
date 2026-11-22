"""HTTP routes for dashboards.

Routes parse/validate input, call the application service, and serialize
output. No business rules live here (architecture doc section 4.1).

* ``/workspaces/{workspace_id}/stats`` --- a workspace's counts and every
  member's workload. Any member; outsiders get ``WORKSPACE_NOT_FOUND``.
* ``/me/stats`` --- the caller's own work, counted, per workspace.

Both take ``?today=YYYY-MM-DD``: the viewer's own day, which "overdue", "due
today" and "due in the next 7 days" are counted from. Without it, today in UTC.
"""

from collections.abc import Mapping
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Query
from fastapi.exceptions import RequestValidationError

from app.modules.auth.dependencies import CurrentUser
from app.modules.insights.dependencies import InsightServiceDep
from app.modules.insights.schemas import (
    InsightPerson,
    InsightWorkspace,
    MemberWorkloadRead,
    MyStatsRead,
    PriorityCountsRead,
    TaskCountsRead,
    WorkspaceStatsRead,
    WorkspaceWorkloadRead,
)
from app.modules.tasks.enums import TaskPriority
from app.modules.tasks.schemas import MAX_DUE_DATE, MIN_DUE_DATE
from app.shared.time import utc_now

router = APIRouter(tags=["insights"])

WorkspaceId = Annotated[UUID, Path(description="Workspace to summarise.")]
Today = Annotated[
    date | None,
    Query(description="The viewer's own day; overdue and due soon are counted from it."),
]


def _day(today: date | None) -> date:
    """The day to count from, within the range a due date may take.

    Outside it, "overdue" would mean nothing, and a date near the edge of the
    calendar could not have seven days added; refused in the framework's own
    ``422 VALIDATION_ERROR`` shape, like any bad parameter.
    """
    if today is None:
        return utc_now().date()
    if not MIN_DUE_DATE <= today <= MAX_DUE_DATE:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("query", "today"),
                    "msg": (
                        f"today must be between {MIN_DUE_DATE.isoformat()} "
                        f"and {MAX_DUE_DATE.isoformat()}."
                    ),
                    "input": today.isoformat(),
                }
            ]
        )
    return today


def _priorities(counts: Mapping[TaskPriority, int]) -> PriorityCountsRead:
    return PriorityCountsRead(
        high=counts[TaskPriority.HIGH],
        medium=counts[TaskPriority.MEDIUM],
        low=counts[TaskPriority.LOW],
    )


@router.get("/workspaces/{workspace_id}/stats", response_model=WorkspaceStatsRead)
def workspace_stats(
    workspace_id: WorkspaceId,
    user: CurrentUser,
    service: InsightServiceDep,
    today: Today = None,
) -> WorkspaceStatsRead:
    """A workspace's dashboard: status counts, what is overdue or due soon, open work
    per priority, and every member's workload. Any member of the workspace."""
    insight = service.workspace_insight(workspace_id, actor=user, today=_day(today))
    return WorkspaceStatsRead(
        workspace_id=insight.workspace.id,
        today=insight.today,
        totals=TaskCountsRead.model_validate(insight.totals),
        open_by_priority=_priorities(insight.open_by_priority),
        workload=[
            MemberWorkloadRead(
                person=InsightPerson.model_validate(load.person) if load.person else None,
                role=load.role,
                counts=TaskCountsRead.model_validate(load.counts),
            )
            for load in insight.workload
        ],
    )


@router.get("/me/stats", response_model=MyStatsRead)
def my_stats(user: CurrentUser, service: InsightServiceDep, today: Today = None) -> MyStatsRead:
    """The caller's own dashboard: their work in every workspace, counted."""
    insight = service.personal_insight(actor=user, today=_day(today))
    return MyStatsRead(
        today=insight.today,
        totals=TaskCountsRead.model_validate(insight.totals),
        open_by_priority=_priorities(insight.open_by_priority),
        by_workspace=[
            WorkspaceWorkloadRead(
                workspace=InsightWorkspace.model_validate(load.workspace),
                counts=TaskCountsRead.model_validate(load.counts),
            )
            for load in insight.by_workspace
        ],
    )
