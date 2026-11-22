"""Unit tests for dashboards: a workspace's and a person's own (``insights``).

Every number is counted on request from the tasks themselves, on the viewer's
own day. The tests pin what each count means --- overdue is open work due before
today; "next 7 days" starts tomorrow --- how workload is listed, which tasks a
person's own dashboard counts, and who may see which dashboard (architecture doc
sections 5 and 9).
"""

from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.insights.service import InsightService
from app.modules.tasks.enums import TaskPriority, TaskStatus
from app.modules.tasks.models import Task
from app.modules.tasks.schemas import TaskCreate
from app.modules.tasks.service import TaskService
from app.modules.tasks.stats import TaskCounts
from app.modules.users.models import User
from app.modules.workspaces.enums import WorkspaceKind, WorkspaceRole
from app.modules.workspaces.exceptions import WorkspaceNotFoundError
from app.modules.workspaces.schemas import InviteCreate, WorkspaceCreate
from app.modules.workspaces.service import WorkspaceService
from tests.synth import PASSWORD, email_for, slug_for

pytestmark = pytest.mark.unit

TODAY = date(2026, 11, 10)


def _register(accounts: AuthService, label: str, name: str) -> User:
    return accounts.register(
        RegisterRequest(email=email_for(label), password=PASSWORD, display_name=name)
    )


class Cast:
    """A company with an owner, two members and a viewer; an outsider elsewhere."""

    def __init__(self, session: Session) -> None:
        accounts = AuthService(session)
        self.workspaces = WorkspaceService(session)
        self.tasks = TaskService(session)
        self.owner = _register(accounts, "dash-owner", "Olive Owner")
        self.ana = _register(accounts, "dash-ana", "Ana Member")
        self.bo = _register(accounts, "dash-bo", "Bo Member")
        self.viewer = _register(accounts, "dash-viewer", "Vi Viewer")
        self.outsider = _register(accounts, "dash-outsider", "Oz Outsider")
        self.team = self.workspaces.create_team(
            WorkspaceCreate(name="Dash Co", slug=slug_for("dash")), actor=self.owner
        )
        for account, role in (
            (self.ana, WorkspaceRole.MEMBER),
            (self.bo, WorkspaceRole.MEMBER),
            (self.viewer, WorkspaceRole.VIEWER),
        ):
            invite = self.workspaces.invite(
                self.team.id, InviteCreate(user_id=account.id, role=role), actor=self.owner
            )
            self.workspaces.accept_invitation(invite.id, actor=account)

    def task(self, title: str, *, in_workspace: Any = None, **fields: Any) -> Task:
        return self.tasks.create_task(
            in_workspace or self.team.id,
            TaskCreate.model_validate({"title": title, **fields}),
            actor=self.owner,
        )


@pytest.fixture()
def cast(session: Session) -> Cast:
    return Cast(session)


@pytest.fixture()
def insights(session: Session) -> InsightService:
    return InsightService(session)


def day(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


# --- what each count means -------------------------------------------------------
def test_counts_by_status_and_by_when_open_work_is_due(
    cast: Cast, insights: InsightService
) -> None:
    cast.task("Late", due_date=day(-1))
    cast.task("Late but done", due_date=day(-3), status=TaskStatus.DONE)
    cast.task("Today", due_date=day(0), status=TaskStatus.IN_PROGRESS)
    cast.task("Tomorrow", due_date=day(1))
    cast.task("In a week", due_date=day(7))
    cast.task("Later", due_date=day(8))
    cast.task("Undated")

    totals = insights.workspace_insight(cast.team.id, actor=cast.owner, today=TODAY).totals

    assert totals == TaskCounts(
        total=7,
        todo=5,
        in_progress=1,
        done=1,
        overdue=1,  # finished work is never overdue
        due_today=1,
        due_next_7_days=2,  # tomorrow through a week from today
    )
    assert totals.open == 6


def test_the_viewers_day_decides_what_is_overdue(cast: Cast, insights: InsightService) -> None:
    cast.task("Due on the 10th", due_date=day(0))

    on_the_day = insights.workspace_insight(cast.team.id, actor=cast.owner, today=TODAY)
    next_day = insights.workspace_insight(
        cast.team.id, actor=cast.owner, today=TODAY + timedelta(days=1)
    )

    assert (on_the_day.totals.due_today, on_the_day.totals.overdue) == (1, 0)
    assert (next_day.totals.due_today, next_day.totals.overdue) == (0, 1)


def test_open_work_is_counted_per_priority(cast: Cast, insights: InsightService) -> None:
    cast.task("Urgent", priority=TaskPriority.HIGH)
    cast.task("Urgent, done", priority=TaskPriority.HIGH, status=TaskStatus.DONE)
    cast.task("Normal")

    insight = insights.workspace_insight(cast.team.id, actor=cast.owner, today=TODAY)

    assert dict(insight.open_by_priority) == {
        TaskPriority.HIGH: 1,
        TaskPriority.MEDIUM: 1,
        TaskPriority.LOW: 0,
    }


# --- workload ------------------------------------------------------------------------
def test_workload_lists_everyone_busiest_first_then_the_unassigned(
    cast: Cast, insights: InsightService
) -> None:
    cast.task("Bo 1", assignee_id=cast.bo.id)
    cast.task("Bo 2", assignee_id=cast.bo.id, due_date=day(-2))
    cast.task("Ana 1", assignee_id=cast.ana.id)
    cast.task("Ana done", assignee_id=cast.ana.id, status=TaskStatus.DONE)
    cast.task("Nobody's")

    workload = insights.workspace_insight(cast.team.id, actor=cast.ana, today=TODAY).workload

    rows = [
        (load.person.display_name if load.person else None, load.role, load.counts.open)
        for load in workload
    ]
    assert rows == [
        ("Bo Member", WorkspaceRole.MEMBER, 2),
        ("Ana Member", WorkspaceRole.MEMBER, 1),
        # Nothing open: still listed, alphabetically --- an empty row is information.
        ("Olive Owner", WorkspaceRole.OWNER, 0),
        ("Vi Viewer", WorkspaceRole.VIEWER, 0),
        (None, None, 1),
    ]
    assert workload[0].counts.overdue == 1
    assert workload[1].counts.done == 1


def test_every_member_sees_the_dashboard_and_outsiders_see_nothing(
    cast: Cast, insights: InsightService
) -> None:
    cast.task("Shared")

    assert (
        insights.workspace_insight(cast.team.id, actor=cast.viewer, today=TODAY).totals.total == 1
    )
    with pytest.raises(WorkspaceNotFoundError):
        insights.workspace_insight(cast.team.id, actor=cast.outsider, today=TODAY)


def test_a_suspended_company_keeps_its_dashboard(cast: Cast, insights: InsightService) -> None:
    cast.task("Frozen")
    cast.workspaces.set_suspended(cast.team.id, suspended=True, note=None)

    assert insights.workspace_insight(cast.team.id, actor=cast.ana, today=TODAY).totals.total == 1


# --- a person's own dashboard -----------------------------------------------------------
def test_a_persons_own_work_is_what_their_list_shows(cast: Cast, insights: InsightService) -> None:
    private = cast.tasks.personal_workspace_id(actor=cast.ana)
    cast.tasks.create_task(private, TaskCreate(title="Errand", due_date=day(-1)), actor=cast.ana)
    cast.task("Assigned", assignee_id=cast.ana.id, due_date=day(0))
    cast.task("Someone else's", assignee_id=cast.bo.id)
    cast.task("Nobody's in the company")

    insight = insights.personal_insight(actor=cast.ana, today=TODAY)
    listed, total = cast.tasks.list_my_tasks(actor=cast.ana)

    assert insight.totals.total == total == 2
    assert {task.title for task in listed} == {"Errand", "Assigned"}
    assert (insight.totals.overdue, insight.totals.due_today) == (1, 1)
    assert [(load.workspace.kind, load.counts.open) for load in insight.by_workspace] == [
        (WorkspaceKind.PERSONAL, 1),
        (WorkspaceKind.TEAM, 1),
    ]


def test_leaving_a_company_takes_its_work_off_the_dashboard(
    cast: Cast, insights: InsightService
) -> None:
    cast.task("Assigned", assignee_id=cast.bo.id)

    cast.workspaces.remove_member(cast.team.id, cast.bo.id, actor=cast.bo)
    insight = insights.personal_insight(actor=cast.bo, today=TODAY)

    assert insight.totals.total == 0
    assert [load.workspace.kind for load in insight.by_workspace] == [WorkspaceKind.PERSONAL]
