"""Unit tests for scheduling reads: due-date filters, orders and "my tasks".

A board and a person's own list share one set of filters: ``open`` (everything
not done), an inclusive window of due dates, and scheduled or unscheduled tasks;
and two more orders, soonest due first and highest priority first. "My tasks" is
what is assigned to the caller in any workspace they may read, plus the
unassigned tasks of their private workspace --- and nothing from a workspace they
are not in (architecture doc sections 6 and 9).
"""

import uuid
from collections.abc import Iterable
from datetime import date
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.labels.schemas import LabelCreate
from app.modules.labels.service import LabelService
from app.modules.tasks.enums import StatusScope, TaskOrder, TaskPriority, TaskStatus
from app.modules.tasks.models import Task
from app.modules.tasks.schemas import TaskCreate
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from app.modules.workspaces.schemas import InviteCreate, WorkspaceCreate
from app.modules.workspaces.service import WorkspaceService
from tests.synth import PASSWORD, email_for, slug_for

pytestmark = pytest.mark.unit


def _register(accounts: AuthService, label: str) -> User:
    return accounts.register(RegisterRequest(email=email_for(label), password=PASSWORD))


class Cast:
    """A company with an owner and a member, their private workspaces, and an outsider."""

    def __init__(self, session: Session) -> None:
        accounts = AuthService(session)
        self.workspaces = WorkspaceService(session)
        self.tasks = TaskService(session)
        self.owner = _register(accounts, "schedule-owner")
        self.member = _register(accounts, "schedule-member")
        self.outsider = _register(accounts, "schedule-outsider")
        self.team = self.workspaces.create_team(
            WorkspaceCreate(name="Schedule Co", slug=slug_for("schedule")), actor=self.owner
        )
        invite = self.workspaces.invite(
            self.team.id, InviteCreate(user_id=self.member.id), actor=self.owner
        )
        self.workspaces.accept_invitation(invite.id, actor=self.member)
        self.elsewhere = self.workspaces.create_team(
            WorkspaceCreate(name="Elsewhere Co", slug=slug_for("schedule-elsewhere")),
            actor=self.outsider,
        )
        self.member_private = self.tasks.personal_workspace_id(actor=self.member)
        self.owner_private = self.tasks.personal_workspace_id(actor=self.owner)

    def task(self, workspace_id: uuid.UUID, actor: User, title: str, **fields: Any) -> Task:
        return self.tasks.create_task(workspace_id, TaskCreate(title=title, **fields), actor=actor)


@pytest.fixture()
def cast(session: Session) -> Cast:
    return Cast(session)


def titles(tasks: Iterable[Task]) -> list[str]:
    return [task.title for task in tasks]


# --- the shared filters -------------------------------------------------------
@pytest.fixture()
def dated(cast: Cast) -> None:
    """Tasks in the company around November 2026, one without a date, one done."""
    for title, due, status in (
        ("Oct 31", date(2026, 10, 31), TaskStatus.TODO),
        ("Nov 1", date(2026, 11, 1), TaskStatus.IN_PROGRESS),
        ("Nov 15", date(2026, 11, 15), TaskStatus.TODO),
        ("Nov 30", date(2026, 11, 30), TaskStatus.DONE),
        ("Dec 1", date(2026, 12, 1), TaskStatus.TODO),
        ("Someday", None, TaskStatus.TODO),
    ):
        cast.task(cast.team.id, cast.owner, title, due_date=due, status=status)


def test_a_due_window_is_inclusive_at_both_ends(cast: Cast, dated: None) -> None:
    items, total = cast.tasks.list_tasks(
        cast.team.id,
        actor=cast.owner,
        due_from=date(2026, 11, 1),
        due_to=date(2026, 11, 30),
        order=TaskOrder.DUE,
    )

    assert (titles(items), total) == (["Nov 1", "Nov 15", "Nov 30"], 3)


def test_a_window_open_at_one_end_never_includes_undated_tasks(cast: Cast, dated: None) -> None:
    items, _ = cast.tasks.list_tasks(
        cast.team.id, actor=cast.owner, due_from=date(2026, 11, 30), order=TaskOrder.DUE
    )

    assert titles(items) == ["Nov 30", "Dec 1"]


def test_scheduled_and_unscheduled(cast: Cast, dated: None) -> None:
    unscheduled, _ = cast.tasks.list_tasks(cast.team.id, actor=cast.owner, has_due_date=False)
    scheduled, total = cast.tasks.list_tasks(cast.team.id, actor=cast.owner, has_due_date=True)

    assert titles(unscheduled) == ["Someday"]
    assert total == 5 and "Someday" not in titles(scheduled)


def test_open_is_everything_not_done(cast: Cast, dated: None) -> None:
    items, total = cast.tasks.list_tasks(
        cast.team.id, actor=cast.owner, status=StatusScope.OPEN, order=TaskOrder.DUE
    )

    assert (titles(items), total) == (["Oct 31", "Nov 1", "Nov 15", "Dec 1", "Someday"], 5)
    done, _ = cast.tasks.list_tasks(cast.team.id, actor=cast.owner, status=TaskStatus.DONE)
    assert titles(done) == ["Nov 30"]


# --- the new orders -----------------------------------------------------------
def test_due_order_is_soonest_first_then_higher_priority_then_undated(cast: Cast) -> None:
    day = date(2026, 11, 10)
    cast.task(cast.team.id, cast.owner, "Undated high", priority=TaskPriority.HIGH)
    cast.task(cast.team.id, cast.owner, "Later", due_date=date(2026, 11, 20))
    cast.task(cast.team.id, cast.owner, "Same day low", due_date=day, priority=TaskPriority.LOW)
    cast.task(cast.team.id, cast.owner, "Same day high", due_date=day, priority=TaskPriority.HIGH)

    items, _ = cast.tasks.list_tasks(cast.team.id, actor=cast.owner, order=TaskOrder.DUE)

    assert titles(items) == ["Same day high", "Same day low", "Later", "Undated high"]


def test_priority_order_is_high_medium_low_soonest_first_inside(cast: Cast) -> None:
    cast.task(cast.team.id, cast.owner, "Low", priority=TaskPriority.LOW)
    cast.task(cast.team.id, cast.owner, "Medium", priority=TaskPriority.MEDIUM)
    cast.task(cast.team.id, cast.owner, "High undated", priority=TaskPriority.HIGH)
    cast.task(
        cast.team.id,
        cast.owner,
        "High soon",
        priority=TaskPriority.HIGH,
        due_date=date(2026, 11, 2),
    )

    items, _ = cast.tasks.list_tasks(cast.team.id, actor=cast.owner, order=TaskOrder.PRIORITY)

    assert titles(items) == ["High soon", "High undated", "Medium", "Low"]


def test_the_new_orders_page_without_gaps_or_repeats(cast: Cast) -> None:
    for index in range(7):
        cast.task(
            cast.team.id,
            cast.owner,
            f"Task {index}",
            due_date=date(2026, 11, 1 + index % 3) if index % 2 else None,
        )

    for order in (TaskOrder.DUE, TaskOrder.PRIORITY):
        seen: list[str] = []
        for page in range(1, 5):
            items, _ = cast.tasks.list_tasks(
                cast.team.id, actor=cast.owner, order=order, page=page, page_size=2
            )
            seen.extend(titles(items))
        assert sorted(seen) == sorted(f"Task {index}" for index in range(7))


# --- my tasks -----------------------------------------------------------------
def test_my_tasks_is_what_is_mine_in_every_workspace(cast: Cast) -> None:
    cast.task(cast.team.id, cast.owner, "Team, mine", assignee_id=cast.member.id)
    cast.task(cast.team.id, cast.owner, "Team, nobody's")
    cast.task(cast.team.id, cast.owner, "Team, the owner's", assignee_id=cast.owner.id)
    cast.task(cast.member_private, cast.member, "Private to-do")
    cast.task(cast.owner_private, cast.owner, "The owner's private to-do")

    items, total = cast.tasks.list_my_tasks(actor=cast.member, order=TaskOrder.NEWEST)

    assert (sorted(titles(items)), total) == (["Private to-do", "Team, mine"], 2)


def test_my_tasks_narrows_to_one_workspace_and_ignores_one_you_are_not_in(cast: Cast) -> None:
    cast.task(cast.team.id, cast.owner, "Team", assignee_id=cast.member.id)
    cast.task(cast.member_private, cast.member, "Private")
    cast.task(cast.elsewhere.id, cast.outsider, "Theirs", assignee_id=cast.outsider.id)

    team, _ = cast.tasks.list_my_tasks(actor=cast.member, workspace=cast.team.id)
    private, _ = cast.tasks.list_my_tasks(actor=cast.member, workspace=cast.member_private)
    foreign, total = cast.tasks.list_my_tasks(actor=cast.member, workspace=cast.elsewhere.id)

    assert (titles(team), titles(private)) == (["Team"], ["Private"])
    assert (list(foreign), total) == ([], 0)


def test_my_tasks_defaults_to_soonest_due_first(cast: Cast) -> None:
    cast.task(cast.member_private, cast.member, "Undated")
    cast.task(cast.member_private, cast.member, "Later", due_date=date(2026, 12, 1))
    cast.task(
        cast.team.id, cast.owner, "Soon", due_date=date(2026, 11, 2), assignee_id=cast.member.id
    )

    items, _ = cast.tasks.list_my_tasks(actor=cast.member)

    assert titles(items) == ["Soon", "Later", "Undated"]


def test_my_tasks_takes_the_shared_filters(cast: Cast, session: Session) -> None:
    bug = LabelService(session).create_label(
        cast.team.id, LabelCreate(name="Bug"), actor=cast.owner
    )
    cast.task(
        cast.team.id,
        cast.owner,
        "Open bug",
        assignee_id=cast.member.id,
        label_ids=[bug.id],
        due_date=date(2026, 11, 5),
    )
    cast.task(
        cast.team.id,
        cast.owner,
        "Fixed bug",
        assignee_id=cast.member.id,
        label_ids=[bug.id],
        status=TaskStatus.DONE,
    )
    cast.task(cast.member_private, cast.member, "Errand", due_date=date(2026, 11, 5))

    open_bugs, _ = cast.tasks.list_my_tasks(
        actor=cast.member, status=StatusScope.OPEN, label=bug.id
    )
    due_that_day, _ = cast.tasks.list_my_tasks(
        actor=cast.member, due_from=date(2026, 11, 5), due_to=date(2026, 11, 5)
    )

    assert titles(open_bugs) == ["Open bug"]
    assert sorted(titles(due_that_day)) == ["Errand", "Open bug"]


def test_leaving_a_company_takes_its_tasks_off_my_list(cast: Cast) -> None:
    cast.task(cast.team.id, cast.owner, "Team work", assignee_id=cast.member.id)
    cast.task(cast.member_private, cast.member, "Private")

    cast.workspaces.remove_member(cast.team.id, cast.member.id, actor=cast.member)

    items, _ = cast.tasks.list_my_tasks(actor=cast.member)
    assert titles(items) == ["Private"]


def test_a_suspended_companys_tasks_stay_readable_on_my_list(cast: Cast) -> None:
    cast.task(cast.team.id, cast.owner, "Frozen work", assignee_id=cast.member.id)
    cast.workspaces.set_suspended(cast.team.id, suspended=True, note=None)

    items, _ = cast.tasks.list_my_tasks(actor=cast.member)

    assert titles(items) == ["Frozen work"]
