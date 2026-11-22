"""Unit tests for the labels module (service rules, without HTTP).

A label lives in one workspace and is reached only through membership of it,
like a project. The rules specific to labels each have tests below: names are
unique per workspace regardless of case, colors come from a fixed palette, a
workspace holds a bounded number of labels, creating, renaming and recoloring
are for owners, admins and managers, deleting is for owners and admins, and
deleting never deletes work --- the label is taken off its tasks in the same
transaction, as a recorded edit (architecture doc sections 6 and 9).

Accounts join companies the way the product does --- invite, then accept --- so
no test relies on a membership state a real caller could not reach.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.activity.enums import ActivityVerb
from app.modules.activity.models import ActivityEvent
from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.labels import repository as label_repository
from app.modules.labels import service as label_service
from app.modules.labels.enums import LabelColor
from app.modules.labels.exceptions import (
    LabelConflictError,
    LabelLimitReachedError,
    LabelNameInUseError,
    LabelNotFoundError,
)
from app.modules.labels.models import Label
from app.modules.labels.schemas import LabelCreate, LabelUpdate
from app.modules.labels.service import LabelService
from app.modules.tasks.exceptions import TaskConflictError
from app.modules.tasks.models import Task, task_labels
from app.modules.tasks.schemas import TaskCreate, TaskUpdate
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from app.modules.workspaces.enums import WorkspaceRole
from app.modules.workspaces.exceptions import (
    WorkspaceNotFoundError,
    WorkspaceRoleNotAllowedError,
    WorkspaceSuspendedError,
)
from app.modules.workspaces.schemas import InviteCreate, WorkspaceCreate
from app.modules.workspaces.service import WorkspaceService
from tests.synth import PASSWORD, email_for, slug_for

pytestmark = pytest.mark.unit


def _register(accounts: AuthService, label: str) -> User:
    return accounts.register(RegisterRequest(email=email_for(label), password=PASSWORD))


class Cast:
    """A company with one person in each role, plus an outsider elsewhere."""

    def __init__(self, session: Session) -> None:
        accounts = AuthService(session)
        self.workspaces = WorkspaceService(session)
        self.owner = _register(accounts, "label-owner")
        self.admin = _register(accounts, "label-admin")
        self.manager = _register(accounts, "label-manager")
        self.member = _register(accounts, "label-member")
        self.viewer = _register(accounts, "label-viewer")
        self.outsider = _register(accounts, "label-outsider")

        self.team = self.workspaces.create_team(
            WorkspaceCreate(name="Label Co", slug=slug_for("labels")), actor=self.owner
        )
        for account, role in (
            (self.admin, WorkspaceRole.ADMIN),
            (self.manager, WorkspaceRole.MANAGER),
            (self.member, WorkspaceRole.MEMBER),
            (self.viewer, WorkspaceRole.VIEWER),
        ):
            invite = self.workspaces.invite(
                self.team.id, InviteCreate(email=account.email, role=role), actor=self.owner
            )
            self.workspaces.accept_invitation(invite.id, actor=account)

        self.elsewhere = self.workspaces.create_team(
            WorkspaceCreate(name="Elsewhere Co", slug=slug_for("labels-elsewhere")),
            actor=self.outsider,
        )


@pytest.fixture()
def cast(session: Session) -> Cast:
    return Cast(session)


@pytest.fixture()
def service(session: Session) -> LabelService:
    return LabelService(session)


@pytest.fixture()
def tasks(session: Session) -> TaskService:
    return TaskService(session)


def _make(
    service: LabelService,
    cast: Cast,
    name: str,
    *,
    color: LabelColor = LabelColor.GRAY,
    actor: User | None = None,
) -> Label:
    return service.create_label(
        cast.team.id, LabelCreate(name=name, color=color), actor=actor or cast.owner
    )


# --- creating and reading --------------------------------------------------
def test_a_manager_can_create_a_label(service: LabelService, cast: Cast) -> None:
    label = service.create_label(
        cast.team.id, LabelCreate(name="  Bug  ", color=LabelColor.RED), actor=cast.manager
    )

    assert label.workspace_id == cast.team.id
    assert (label.name, label.color, label.version) == ("Bug", LabelColor.RED, 1)
    assert label.created_by is not None and label.created_by.id == cast.manager.id


@pytest.mark.parametrize("role", ["member", "viewer"])
def test_members_and_viewers_read_labels_but_cannot_shape_them(
    service: LabelService, cast: Cast, role: str
) -> None:
    """Tagging a task is editing the task; the workspace's labels are not."""
    actor = getattr(cast, role)
    label = _make(service, cast, "Bug")

    assert service.get_label(label.id, actor=actor).name == "Bug"
    assert service.list_labels(cast.team.id, actor=actor)[1] == 1
    for attempt in (
        lambda: _make(service, cast, "Mine", actor=actor),
        lambda: service.update_label(label.id, LabelUpdate(color=LabelColor.GREEN), actor=actor),
        lambda: service.delete_label(label.id, actor=actor),
    ):
        with pytest.raises(WorkspaceRoleNotAllowedError):
            attempt()
    assert service.get_label(label.id, actor=cast.owner).color is LabelColor.GRAY


def test_a_new_label_is_gray_unless_told_otherwise(service: LabelService, cast: Cast) -> None:
    label = service.create_label(cast.team.id, LabelCreate(name="Plain"), actor=cast.owner)

    assert label.color is LabelColor.GRAY


def test_a_label_outside_your_workspace_reads_as_missing(service: LabelService, cast: Cast) -> None:
    label = _make(service, cast, "Internal")

    for attempt in (
        lambda: service.get_label(label.id, actor=cast.outsider),
        lambda: service.update_label(label.id, LabelUpdate(name="Mine"), actor=cast.outsider),
        lambda: service.delete_label(label.id, actor=cast.outsider),
        lambda: service.get_label(uuid.uuid4(), actor=cast.owner),
    ):
        with pytest.raises(LabelNotFoundError):
            attempt()


def test_an_outsider_cannot_list_or_create_in_the_workspace(
    service: LabelService, cast: Cast
) -> None:
    with pytest.raises(WorkspaceNotFoundError):
        service.list_labels(cast.team.id, actor=cast.outsider)
    with pytest.raises(WorkspaceNotFoundError):
        service.create_label(cast.team.id, LabelCreate(name="Sneaky"), actor=cast.outsider)


def test_list_is_alphabetical_ignoring_case_and_stays_in_its_tenant(
    service: LabelService, cast: Cast
) -> None:
    for name in ("bug", "Alpha", "docs"):
        _make(service, cast, name)
    service.create_label(cast.elsewhere.id, LabelCreate(name="Aardvark"), actor=cast.outsider)

    rows, total, pages = service.list_labels(cast.team.id, actor=cast.member)

    assert [label.name for label, _ in rows] == ["Alpha", "bug", "docs"]
    assert (total, pages) == (3, 1)


def test_list_counts_the_tasks_carrying_each_label(
    service: LabelService, tasks: TaskService, cast: Cast
) -> None:
    busy = _make(service, cast, "Busy")
    idle = _make(service, cast, "Idle")
    for title in ("One", "Two"):
        tasks.create_task(
            cast.team.id, TaskCreate(title=title, label_ids=[busy.id]), actor=cast.owner
        )
    tasks.create_task(cast.team.id, TaskCreate(title="Plain"), actor=cast.owner)

    rows, _, _ = service.list_labels(cast.team.id, actor=cast.owner)
    counts = {label.id: count for label, count in rows}

    assert counts == {busy.id: 2, idle.id: 0}


# --- names and colors ------------------------------------------------------
@pytest.mark.parametrize("taken", ["Bug", "bug", "BUG", "  Bug "])
def test_names_are_unique_per_workspace_regardless_of_case(
    service: LabelService, cast: Cast, taken: str
) -> None:
    _make(service, cast, "Bug")

    with pytest.raises(LabelNameInUseError):
        _make(service, cast, taken)


def test_case_folding_is_unicode_aware_on_every_database(service: LabelService, cast: Cast) -> None:
    """SQLite's lower() would miss both of these; the stored key does not."""
    _make(service, cast, "Ärger")
    _make(service, cast, "Straße")

    with pytest.raises(LabelNameInUseError):
        _make(service, cast, "ärger")
    with pytest.raises(LabelNameInUseError):
        _make(service, cast, "STRASSE")


def test_the_same_name_is_fine_in_another_workspace(service: LabelService, cast: Cast) -> None:
    _make(service, cast, "Bug")

    other = service.create_label(cast.elsewhere.id, LabelCreate(name="Bug"), actor=cast.outsider)

    assert other.workspace_id == cast.elsewhere.id


def test_the_database_settles_a_race_for_the_same_name(
    service: LabelService, cast: Cast, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two creates that both pass the friendly check: the constraint refuses one."""
    _make(service, cast, "Urgent")
    monkeypatch.setattr(label_repository, "name_taken", lambda *args, **kwargs: False)

    with pytest.raises(LabelNameInUseError):
        _make(service, cast, "URGENT")

    # The failed insert was rolled back; the session is usable and nothing leaked.
    rows, total, _ = service.list_labels(cast.team.id, actor=cast.owner)
    assert total == 1 and rows[0][0].name == "Urgent"


def test_renaming_onto_another_labels_name_is_refused(service: LabelService, cast: Cast) -> None:
    _make(service, cast, "Bug")
    docs = _make(service, cast, "Docs")

    with pytest.raises(LabelNameInUseError):
        service.update_label(docs.id, LabelUpdate(name="BUG"), actor=cast.manager)


def test_rename_and_recolor_touch_only_supplied_fields(service: LabelService, cast: Cast) -> None:
    label = _make(service, cast, "bug", color=LabelColor.RED)

    renamed = service.update_label(label.id, LabelUpdate(name="Bug"), actor=cast.manager)
    assert (renamed.name, renamed.name_key, renamed.color) == ("Bug", "bug", LabelColor.RED)

    recolored = service.update_label(
        label.id, LabelUpdate(color=LabelColor.ORANGE), actor=cast.manager
    )
    assert (recolored.name, recolored.color, recolored.version) == (
        "Bug",
        LabelColor.ORANGE,
        3,
    )


def test_a_stale_version_is_a_conflict(service: LabelService, cast: Cast) -> None:
    label = _make(service, cast, "Contested")
    seen = label.version
    service.update_label(label.id, LabelUpdate(name="First"), actor=cast.manager)

    with pytest.raises(LabelConflictError):
        service.update_label(label.id, LabelUpdate(name="Second", version=seen), actor=cast.owner)
    with pytest.raises(LabelConflictError):
        service.delete_label(label.id, actor=cast.owner, version=seen)

    assert service.get_label(label.id, actor=cast.owner).name == "First"


# --- the limit -------------------------------------------------------------
def test_a_workspace_holds_a_bounded_number_of_labels(
    service: LabelService, cast: Cast, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(label_service, "MAX_LABELS_PER_WORKSPACE", 2)
    first = _make(service, cast, "One")
    _make(service, cast, "Two")

    with pytest.raises(LabelLimitReachedError) as refused:
        _make(service, cast, "Three")
    assert "2 labels" in refused.value.message

    # Another tenant is not affected, and deleting one makes room again.
    service.create_label(cast.elsewhere.id, LabelCreate(name="Three"), actor=cast.outsider)
    service.delete_label(first.id, actor=cast.owner)
    assert _make(service, cast, "Three").name == "Three"


# --- deleting --------------------------------------------------------------
def test_managers_cannot_delete_but_owners_and_admins_can(
    service: LabelService, cast: Cast
) -> None:
    """Deleting changes everyone's work at once: a manager shapes, never deletes."""
    by_admin = _make(service, cast, "Admin's to delete")
    by_owner = _make(service, cast, "Owner's to delete")

    with pytest.raises(WorkspaceRoleNotAllowedError):
        service.delete_label(by_admin.id, actor=cast.manager)

    service.delete_label(by_admin.id, actor=cast.admin)
    service.delete_label(by_owner.id, actor=cast.owner)

    _, total, _ = service.list_labels(cast.team.id, actor=cast.owner)
    assert total == 0


def test_deleting_a_label_takes_it_off_its_tasks_and_keeps_them(
    service: LabelService, tasks: TaskService, cast: Cast, session: Session
) -> None:
    doomed = _make(service, cast, "Doomed")
    kept = _make(service, cast, "Kept")
    both = tasks.create_task(
        cast.team.id, TaskCreate(title="Both", label_ids=[doomed.id, kept.id]), actor=cast.member
    )
    untouched = tasks.create_task(
        cast.team.id, TaskCreate(title="Only kept", label_ids=[kept.id]), actor=cast.member
    )
    before = (both.version, untouched.version)

    service.delete_label(doomed.id, actor=cast.admin)

    survivor = session.get(Task, both.id)
    assert survivor is not None
    assert [label.name for label in survivor.labels] == ["Kept"]
    # Recorded like any other save: a new version, by whoever deleted the label.
    assert survivor.version == before[0] + 1
    assert survivor.updated_by_id == cast.admin.id
    assert tasks.get_task(untouched.id, actor=cast.owner).version == before[1]
    assert session.get(Label, doomed.id) is None
    assert (
        session.execute(select(task_labels).where(task_labels.c.label_id == doomed.id)).all() == []
    )


def test_deleting_a_label_records_each_detach_with_the_old_name(
    service: LabelService, tasks: TaskService, cast: Cast, session: Session
) -> None:
    doomed = _make(service, cast, "Sunset")
    kept = _make(service, cast, "Alpha")
    task = tasks.create_task(
        cast.team.id, TaskCreate(title="Tagged", label_ids=[doomed.id, kept.id]), actor=cast.owner
    )

    service.delete_label(doomed.id, actor=cast.owner)

    last = session.scalars(
        select(ActivityEvent)
        .where(ActivityEvent.task_id == task.id)
        .order_by(ActivityEvent.created_at.desc(), ActivityEvent.id.desc())
    ).first()
    assert last is not None
    assert last.verb is ActivityVerb.TASK_UPDATED
    assert last.task_version == task.version
    assert last.changes == {
        "labels": {
            "from": [
                {"id": str(kept.id), "name": "Alpha"},
                {"id": str(doomed.id), "name": "Sunset"},
            ],
            "to": [{"id": str(kept.id), "name": "Alpha"}],
        }
    }


def test_an_editor_holding_the_old_version_gets_a_conflict_after_detach(
    service: LabelService, tasks: TaskService, cast: Cast
) -> None:
    """A stale save must not write a deleted label back onto a task."""
    doomed = _make(service, cast, "Going away")
    task = tasks.create_task(
        cast.team.id, TaskCreate(title="Open in a tab", label_ids=[doomed.id]), actor=cast.owner
    )
    seen = task.version

    service.delete_label(doomed.id, actor=cast.owner)

    with pytest.raises(TaskConflictError):
        tasks.update_task(task.id, TaskUpdate(title="Stale", version=seen), actor=cast.manager)


def test_deleting_an_unused_label_changes_no_task(
    service: LabelService, tasks: TaskService, cast: Cast
) -> None:
    unused = _make(service, cast, "Unused")
    task = tasks.create_task(cast.team.id, TaskCreate(title="Plain"), actor=cast.owner)

    service.delete_label(unused.id, actor=cast.owner)

    assert tasks.get_task(task.id, actor=cast.owner).version == task.version


# --- view mode -------------------------------------------------------------
def test_a_suspended_company_keeps_its_labels_readable_and_frozen(
    service: LabelService, cast: Cast
) -> None:
    label = _make(service, cast, "Frozen")
    cast.workspaces.set_suspended(cast.team.id, suspended=True, note=None)

    assert service.get_label(label.id, actor=cast.member).name == "Frozen"
    assert service.list_labels(cast.team.id, actor=cast.member)[1] == 1
    for attempt in (
        lambda: _make(service, cast, "New", actor=cast.manager),
        lambda: service.update_label(label.id, LabelUpdate(name="Thaw"), actor=cast.owner),
        lambda: service.delete_label(label.id, actor=cast.owner),
    ):
        with pytest.raises(WorkspaceSuspendedError):
            attempt()


def test_a_private_workspace_has_labels_too(
    service: LabelService, tasks: TaskService, cast: Cast
) -> None:
    private = tasks.personal_workspace_id(actor=cast.member)

    label = service.create_label(private, LabelCreate(name="Errand"), actor=cast.member)
    service.delete_label(label.id, actor=cast.member)

    with pytest.raises(LabelNotFoundError):
        service.get_label(label.id, actor=cast.member)
