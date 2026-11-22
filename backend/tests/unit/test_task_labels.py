"""Unit tests for labelling tasks (service rules, without HTTP).

A task carries any number of *its own workspace's* labels, up to a limit. The
tests below cover setting and replacing them, the rule that a label from
elsewhere reads exactly like a missing one, that a labels-only save is versioned
like any other, the label filter, and what the activity log says (architecture
doc sections 6 and 9).
"""

import uuid
from collections.abc import Iterable

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.activity.models import ActivityEvent
from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.labels.enums import LabelColor
from app.modules.labels.models import Label
from app.modules.labels.schemas import LabelCreate, LabelUpdate
from app.modules.labels.service import LabelService
from app.modules.tasks.enums import LabelScope, TaskOrder
from app.modules.tasks.exceptions import LabelNotInWorkspaceError, TaskConflictError
from app.modules.tasks.models import Task, task_labels
from app.modules.tasks.schemas import TaskCreate, TaskUpdate
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from tests.synth import PASSWORD, email_for

pytestmark = pytest.mark.unit


def _register(accounts: AuthService, label: str) -> User:
    return accounts.register(RegisterRequest(email=email_for(label), password=PASSWORD))


class Cast:
    """Two people with private workspaces, and labels in each."""

    def __init__(self, session: Session) -> None:
        accounts = AuthService(session)
        self.owner = _register(accounts, "tagging-owner")
        self.other = _register(accounts, "tagging-other")
        tasks = TaskService(session)
        self.labels = LabelService(session)
        self.ws = tasks.personal_workspace_id(actor=self.owner)
        self.other_ws = tasks.personal_workspace_id(actor=self.other)

        def make(name: str, workspace: uuid.UUID, actor: User) -> Label:
            return self.labels.create_label(
                workspace, LabelCreate(name=name, color=LabelColor.BLUE), actor=actor
            )

        self.bug = make("bug", self.ws, self.owner)
        self.api = make("API", self.ws, self.owner)
        self.docs = make("Docs", self.ws, self.owner)
        self.foreign = make("Theirs", self.other_ws, self.other)


@pytest.fixture()
def cast(session: Session) -> Cast:
    return Cast(session)


@pytest.fixture()
def service(session: Session) -> TaskService:
    return TaskService(session)


def names(task: Task) -> list[str]:
    return [label.name for label in task.labels]


def titles(tasks: Iterable[Task]) -> list[str]:
    return [task.title for task in tasks]


# --- setting labels ----------------------------------------------------------
def test_a_task_is_created_with_its_labels_alphabetically(service: TaskService, cast: Cast) -> None:
    task = service.create_task(
        cast.ws,
        TaskCreate(title="Tagged", label_ids=[cast.docs.id, cast.bug.id, cast.api.id]),
        actor=cast.owner,
    )

    assert names(task) == ["API", "bug", "Docs"]


def test_new_tasks_carry_no_labels_by_default(service: TaskService, cast: Cast) -> None:
    task = service.create_task(cast.ws, TaskCreate(title="Plain"), actor=cast.owner)

    assert task.labels == []


def test_a_repeated_label_is_carried_once(service: TaskService, cast: Cast) -> None:
    task = service.create_task(
        cast.ws, TaskCreate(title="Twice", label_ids=[cast.bug.id, cast.bug.id]), actor=cast.owner
    )

    assert names(task) == ["bug"]


def test_another_workspaces_label_reads_exactly_like_a_missing_one(
    service: TaskService, cast: Cast, session: Session
) -> None:
    errors = []
    for candidate in (cast.foreign.id, uuid.uuid4()):
        with pytest.raises(LabelNotInWorkspaceError) as refused:
            service.create_task(
                cast.ws,
                TaskCreate(title="Mislabelled", label_ids=[cast.bug.id, candidate]),
                actor=cast.owner,
            )
        errors.append((refused.value.code, refused.value.message))

    assert errors[0] == errors[1]
    assert session.scalars(select(Task).where(Task.title == "Mislabelled")).first() is None


def test_update_replaces_the_labels_and_omitting_them_keeps_them(
    service: TaskService, cast: Cast
) -> None:
    task = service.create_task(
        cast.ws, TaskCreate(title="Relabel", label_ids=[cast.bug.id]), actor=cast.owner
    )

    replaced = service.update_task(
        task.id, TaskUpdate(label_ids=[cast.docs.id, cast.api.id]), actor=cast.owner
    )
    assert names(replaced) == ["API", "Docs"]

    renamed = service.update_task(task.id, TaskUpdate(title="Renamed"), actor=cast.owner)
    assert names(renamed) == ["API", "Docs"]

    cleared = service.update_task(task.id, TaskUpdate(label_ids=[]), actor=cast.owner)
    assert cleared.labels == []


def test_relabelling_with_a_foreign_label_changes_nothing(
    service: TaskService, cast: Cast, session: Session
) -> None:
    task = service.create_task(
        cast.ws, TaskCreate(title="Guarded", label_ids=[cast.bug.id]), actor=cast.owner
    )

    with pytest.raises(LabelNotInWorkspaceError):
        service.update_task(task.id, TaskUpdate(label_ids=[cast.foreign.id]), actor=cast.owner)

    session.expire_all()
    assert names(service.get_task(task.id, actor=cast.owner)) == ["bug"]


# --- versions ----------------------------------------------------------------
def test_a_labels_only_save_is_a_new_version(service: TaskService, cast: Cast) -> None:
    """The link table is invisible to the version column; the save must not be.

    The task's editor is already the person saving, so no column would change
    on its own: only the label change can move the version here.
    """
    task = service.create_task(cast.ws, TaskCreate(title="Versioned"), actor=cast.owner)
    service.update_task(task.id, TaskUpdate(title="Versioned twice"), actor=cast.owner)
    seen = service.get_task(task.id, actor=cast.owner).version

    saved = service.update_task(
        task.id, TaskUpdate(label_ids=[cast.bug.id], version=seen), actor=cast.owner
    )

    assert saved.version == seen + 1
    assert names(saved) == ["bug"]


def test_a_labels_only_save_loses_a_race_like_any_other(
    service: TaskService, cast: Cast, session: Session
) -> None:
    """Two tabs relabelling the same version: the database refuses the second.

    The version check inside the service is bypassed by reading the task at the
    old version, then letting another save win first --- exactly what a lost race
    looks like at flush.
    """
    task = service.create_task(cast.ws, TaskCreate(title="Raced"), actor=cast.owner)
    service.update_task(task.id, TaskUpdate(title="Raced again"), actor=cast.owner)
    session.commit()
    # Another writer moves the row on underneath this session, which still holds
    # the version it read.
    session.execute(
        update(Task).where(Task.id == task.id).values(version=Task.version + 1),
        execution_options={"synchronize_session": False},
    )

    with pytest.raises(TaskConflictError):
        service.update_task(task.id, TaskUpdate(label_ids=[cast.docs.id]), actor=cast.owner)


def test_saving_the_same_labels_is_not_a_change(service: TaskService, cast: Cast) -> None:
    task = service.create_task(
        cast.ws, TaskCreate(title="Same", label_ids=[cast.bug.id, cast.api.id]), actor=cast.owner
    )
    # Make the task's editor the same person, so nothing else would bump it.
    service.update_task(task.id, TaskUpdate(title="Same again"), actor=cast.owner)
    seen = service.get_task(task.id, actor=cast.owner).version

    again = service.update_task(
        task.id, TaskUpdate(label_ids=[cast.api.id, cast.bug.id]), actor=cast.owner
    )

    assert again.version == seen


def test_relabelling_with_a_stale_version_is_a_conflict(service: TaskService, cast: Cast) -> None:
    task = service.create_task(cast.ws, TaskCreate(title="Contested"), actor=cast.owner)
    service.update_task(task.id, TaskUpdate(label_ids=[cast.bug.id]), actor=cast.owner)

    with pytest.raises(TaskConflictError):
        service.update_task(
            task.id, TaskUpdate(label_ids=[cast.docs.id], version=1), actor=cast.owner
        )

    assert names(service.get_task(task.id, actor=cast.owner)) == ["bug"]


def test_renaming_a_label_shows_on_its_tasks_without_changing_them(
    service: TaskService, cast: Cast, session: Session
) -> None:
    task = service.create_task(
        cast.ws, TaskCreate(title="Renamed label", label_ids=[cast.bug.id]), actor=cast.owner
    )

    cast.labels.update_label(cast.bug.id, LabelUpdate(name="Defect"), actor=cast.owner)

    session.expire_all()
    reread = service.get_task(task.id, actor=cast.owner)
    assert (names(reread), reread.version) == (["Defect"], task.version)


def test_deleting_a_task_removes_its_links_and_keeps_the_labels(
    service: TaskService, cast: Cast, session: Session
) -> None:
    task = service.create_task(
        cast.ws, TaskCreate(title="Doomed", label_ids=[cast.bug.id]), actor=cast.owner
    )

    service.delete_task(task.id, actor=cast.owner)

    assert session.execute(select(task_labels).where(task_labels.c.task_id == task.id)).all() == []
    assert session.get(Label, cast.bug.id) is not None


# --- the filter --------------------------------------------------------------
@pytest.fixture()
def spread(service: TaskService, cast: Cast) -> None:
    """Tasks with one, two and no labels."""
    for title, label_ids in (
        ("Bug only", [cast.bug.id]),
        ("Bug and docs", [cast.bug.id, cast.docs.id]),
        ("Bare", []),
    ):
        service.create_task(cast.ws, TaskCreate(title=title, label_ids=label_ids), actor=cast.owner)


def test_filter_by_a_label_and_by_none(service: TaskService, cast: Cast, spread: None) -> None:
    tagged, total = service.list_tasks(cast.ws, actor=cast.owner, label=cast.bug.id)
    assert (sorted(titles(tagged)), total) == (["Bug and docs", "Bug only"], 2)

    bare, total = service.list_tasks(cast.ws, actor=cast.owner, label=LabelScope.NONE)
    assert (titles(bare), total) == (["Bare"], 1)


def test_filtering_by_a_foreign_label_finds_nothing(
    service: TaskService, cast: Cast, spread: None
) -> None:
    items, total = service.list_tasks(cast.ws, actor=cast.owner, label=cast.foreign.id)

    assert (list(items), total) == ([], 0)


def test_a_task_with_many_labels_is_listed_and_counted_once(
    service: TaskService, cast: Cast
) -> None:
    """Labels are loaded beside the page, never joined into it."""
    for index in range(3):
        service.create_task(
            cast.ws,
            TaskCreate(title=f"Busy {index}", label_ids=[cast.bug.id, cast.api.id, cast.docs.id]),
            actor=cast.owner,
        )

    first, total = service.list_tasks(cast.ws, actor=cast.owner, page=1, page_size=2)
    second, _ = service.list_tasks(cast.ws, actor=cast.owner, page=2, page_size=2)

    assert total == 3
    assert sorted(titles([*first, *second])) == ["Busy 0", "Busy 1", "Busy 2"]
    assert all(names(task) == ["API", "bug", "Docs"] for task in [*first, *second])


def test_the_label_filter_combines_with_the_project_order(
    service: TaskService, cast: Cast, spread: None
) -> None:
    items, total = service.list_tasks(
        cast.ws, actor=cast.owner, label=cast.docs.id, order=TaskOrder.PROJECT
    )

    assert (titles(items), total) == (["Bug and docs"], 1)


# --- the activity log --------------------------------------------------------
def _events(session: Session, task_id: uuid.UUID) -> list[ActivityEvent]:
    return list(
        session.scalars(
            select(ActivityEvent)
            .where(ActivityEvent.task_id == task_id)
            .order_by(ActivityEvent.created_at, ActivityEvent.id)
        ).all()
    )


def _ref(label: Label) -> dict[str, str]:
    return {"id": str(label.id), "name": label.name}


def test_creating_a_labelled_task_records_its_labels(
    service: TaskService, cast: Cast, session: Session
) -> None:
    task = service.create_task(
        cast.ws,
        TaskCreate(title="Born tagged", label_ids=[cast.docs.id, cast.api.id]),
        actor=cast.owner,
    )

    [created] = _events(session, task.id)
    assert created.changes["labels"] == {"from": [], "to": [_ref(cast.api), _ref(cast.docs)]}


def test_creating_an_unlabelled_task_says_nothing_about_labels(
    service: TaskService, cast: Cast, session: Session
) -> None:
    task = service.create_task(cast.ws, TaskCreate(title="Plain"), actor=cast.owner)

    [created] = _events(session, task.id)
    assert "labels" not in created.changes


def test_relabelling_records_the_whole_set_before_and_after(
    service: TaskService, cast: Cast, session: Session
) -> None:
    task = service.create_task(
        cast.ws, TaskCreate(title="Relabel", label_ids=[cast.bug.id]), actor=cast.owner
    )

    saved = service.update_task(
        task.id, TaskUpdate(label_ids=[cast.bug.id, cast.api.id]), actor=cast.owner
    )

    last = _events(session, task.id)[-1]
    assert last.changes == {
        "labels": {"from": [_ref(cast.bug)], "to": [_ref(cast.api), _ref(cast.bug)]}
    }
    assert last.task_version == saved.version


def test_saving_the_same_labels_records_nothing(
    service: TaskService, cast: Cast, session: Session
) -> None:
    task = service.create_task(
        cast.ws, TaskCreate(title="Quiet", label_ids=[cast.bug.id]), actor=cast.owner
    )

    service.update_task(task.id, TaskUpdate(label_ids=[cast.bug.id]), actor=cast.owner)

    assert len(_events(session, task.id)) == 1
