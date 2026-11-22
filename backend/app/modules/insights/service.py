"""Application service for dashboards: a workspace's, and a person's own.

Reading only, and nothing is stored or cached: every number is counted on the
request that shows it, so a dashboard can never disagree with the list it links
to. Who may see one is the access policy's decision:

===============================  ==========  =====================================
Dashboard                        Action      Counts
===============================  ==========  =====================================
A workspace's                    ``read``    every task in it, per member
A person's own                   ---         their own work in every workspace they
                                             may read, per workspace
===============================  ==========  =====================================

Every member of a company sees its dashboard, workload included: they can already
read every task and who holds it, so the summary reveals nothing new. A suspended
company's stays readable (view mode). A workspace the caller is not in answers
``WORKSPACE_NOT_FOUND``, like everywhere else.

"Today" is the viewer's own day, sent by the client --- overdue is a question of
the calendar on the wall, not of the server's timezone --- and defaults to today in
UTC.
"""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.modules.tasks import stats
from app.modules.tasks.enums import TaskPriority
from app.modules.tasks.service import TaskService
from app.modules.tasks.stats import NO_TASKS, TaskCounts
from app.modules.users.models import User
from app.modules.workspaces.access import WorkspaceAccessPolicy
from app.modules.workspaces.enums import WorkspaceAction, WorkspaceRole
from app.modules.workspaces.models import Workspace
from app.modules.workspaces.roster import roster


@dataclass(frozen=True)
class MemberLoad:
    """One person's share of a workspace's work; ``person`` is ``None`` for the
    tasks nobody holds."""

    person: User | None
    role: WorkspaceRole | None
    counts: TaskCounts


@dataclass(frozen=True)
class WorkspaceInsight:
    workspace: Workspace
    today: date
    totals: TaskCounts
    open_by_priority: Mapping[TaskPriority, int]
    workload: Sequence[MemberLoad]


@dataclass(frozen=True)
class WorkspaceLoad:
    """How much of a person's own work lives in one of their workspaces."""

    workspace: Workspace
    counts: TaskCounts


@dataclass(frozen=True)
class PersonalInsight:
    today: date
    totals: TaskCounts
    open_by_priority: Mapping[TaskPriority, int]
    by_workspace: Sequence[WorkspaceLoad]


class InsightService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._access = WorkspaceAccessPolicy(session)
        self._tasks = TaskService(session)

    def workspace_insight(
        self, workspace_id: uuid.UUID, *, actor: User, today: date
    ) -> WorkspaceInsight:
        """A workspace's counts, with every member's workload.

        Members come busiest first --- most open work, then most overdue --- and
        alphabetically among equals, so the people who may need help lead the
        list. Everyone is listed, with no tasks too: an empty row is information.
        The tasks nobody holds come last, as their own row.
        """
        access = self._access.require(workspace_id, actor=actor, action=WorkspaceAction.READ)
        breakdown = stats.workspace_breakdown(self._session, access.workspace.id, today=today)
        people = [
            MemberLoad(person=account, role=role, counts=breakdown.groups.get(account.id, NO_TASKS))
            for account, role in roster(self._session, access.workspace.id)
        ]
        # ``sorted`` is stable: people with the same load stay alphabetical.
        people = sorted(people, key=lambda load: (-load.counts.open, -load.counts.overdue))
        unassigned = MemberLoad(person=None, role=None, counts=breakdown.groups.get(None, NO_TASKS))
        return WorkspaceInsight(
            workspace=access.workspace,
            today=today,
            totals=breakdown.totals,
            open_by_priority=breakdown.open_by_priority,
            workload=[*people, unassigned],
        )

    def personal_insight(self, *, actor: User, today: date) -> PersonalInsight:
        """The caller's own work --- what ``/me/tasks`` lists --- counted, per workspace.

        Workspaces come in the order the switcher shows them, private first, each
        with the share of the caller's work it holds, including none.
        """
        scope = self._tasks.my_scope(actor=actor)
        breakdown = stats.personal_breakdown(
            self._session,
            user_id=actor.id,
            workspace_ids=[access.workspace.id for access in scope.accesses],
            personal_workspace_id=scope.personal_workspace_id,
            today=today,
        )
        return PersonalInsight(
            today=today,
            totals=breakdown.totals,
            open_by_priority=breakdown.open_by_priority,
            by_workspace=[
                WorkspaceLoad(
                    workspace=access.workspace,
                    counts=breakdown.groups.get(access.workspace.id, NO_TASKS),
                )
                for access in scope.accesses
            ],
        )
