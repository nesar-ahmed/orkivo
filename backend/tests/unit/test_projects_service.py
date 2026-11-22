"""Unit tests for the projects module (service rules, without HTTP).

A project lives in one workspace and is reached only through membership of it,
like a task. Four rules are specific to projects, and each has tests below:
names are unique per workspace regardless of case, creating and renaming are for
owners, admins and managers, deleting is for owners and admins, and deleting
never deletes work --- the tasks are detached in the same transaction
(architecture doc sections 6 and 9).

Accounts join companies the way the product does --- invite, then accept --- so
no test relies on a membership state a real caller could not reach.
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.projects import repository as project_repository
from app.modules.projects.exceptions import (
    ProjectConflictError,
    ProjectNameInUseError,
    ProjectNotFoundError,
)
from app.modules.projects.models import Project
from app.modules.projects.schemas import ProjectCreate, ProjectUpdate
from app.modules.projects.service import ProjectService
from app.modules.tasks.enums import TaskStatus
from app.modules.tasks.exceptions import TaskConflictError
from app.modules.tasks.models import Task
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
        self.owner = _register(accounts, "project-owner")
        self.admin = _register(accounts, "project-admin")
        self.manager = _register(accounts, "project-manager")
        self.member = _register(accounts, "project-member")
        self.viewer = _register(accounts, "project-viewer")
        self.outsider = _register(accounts, "project-outsider")

        self.team = self.workspaces.create_team(
            WorkspaceCreate(name="Project Co", slug=slug_for("projects")), actor=self.owner
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
            WorkspaceCreate(name="Elsewhere Co", slug=slug_for("projects-elsewhere")),
            actor=self.outsider,
        )


@pytest.fixture()
def cast(session: Session) -> Cast:
    return Cast(session)


@pytest.fixture()
def service(session: Session) -> ProjectService:
    return ProjectService(session)


@pytest.fixture()
def tasks(session: Session) -> TaskService:
    return TaskService(session)


def _make(
    service: ProjectService, cast: Cast, name: str, *, actor: User | None = None
) -> Project:
    return service.create_project(
        cast.team.id, ProjectCreate(name=name), actor=actor or cast.owner
    )


# --- creating and reading --------------------------------------------------
def test_a_manager_can_create_a_project(service: ProjectService, cast: Cast) -> None:
    project = service.create_project(
        cast.team.id,
        ProjectCreate(name="  Website relaunch  ", description="Q4"),
        actor=cast.manager,
    )

    assert project.workspace_id == cast.team.id
    assert project.name == "Website relaunch"
    assert project.description == "Q4"
    assert project.version == 1
    assert project.created_by is not None and project.created_by.id == cast.manager.id


@pytest.mark.parametrize("role", ["member", "viewer"])
def test_members_and_viewers_read_projects_but_cannot_shape_them(
    service: ProjectService, cast: Cast, role: str
) -> None:
    """Filing a task under a project is editing the task; the set of projects is not."""
    actor = getattr(cast, role)
    project = _make(service, cast, "Website")

    assert service.get_project(project.id, actor=actor).name == "Website"
    assert service.list_projects(cast.team.id, actor=actor)[1] == 1
    for attempt in (
        lambda: _make(service, cast, "Mine", actor=actor),
        lambda: service.update_project(project.id, ProjectUpdate(name="Renamed"), actor=actor),
        lambda: service.delete_project(project.id, actor=actor),
    ):
        with pytest.raises(WorkspaceRoleNotAllowedError):
            attempt()
    assert service.get_project(project.id, actor=cast.owner).name == "Website"


def test_a_project_outside_your_workspace_reads_as_missing(
    service: ProjectService, cast: Cast
) -> None:
    project = _make(service, cast, "Internal")

    for attempt in (
        lambda: service.get_project(project.id, actor=cast.outsider),
        lambda: service.update_project(
            project.id, ProjectUpdate(name="Mine"), actor=cast.outsider
        ),
        lambda: service.delete_project(project.id, actor=cast.outsider),
        lambda: service.get_project(uuid.uuid4(), actor=cast.owner),
    ):
        with pytest.raises(ProjectNotFoundError):
            attempt()


def test_an_outsider_cannot_list_or_create_in_the_workspace(
    service: ProjectService, cast: Cast
) -> None:
    with pytest.raises(WorkspaceNotFoundError):
        service.list_projects(cast.team.id, actor=cast.outsider)
    with pytest.raises(WorkspaceNotFoundError):
        service.create_project(cast.team.id, ProjectCreate(name="Sneaky"), actor=cast.outsider)


def test_list_is_alphabetical_ignoring_case_and_stays_in_its_tenant(
    service: ProjectService, cast: Cast
) -> None:
    for name in ("beta", "Alpha", "gamma"):
        _make(service, cast, name)
    service.create_project(cast.elsewhere.id, ProjectCreate(name="Aardvark"), actor=cast.outsider)

    rows, total, pages = service.list_projects(cast.team.id, actor=cast.member)

    assert [project.name for project, _ in rows] == ["Alpha", "beta", "gamma"]
    assert (total, pages) == (3, 1)


def test_list_counts_all_and_open_tasks(
    service: ProjectService, tasks: TaskService, cast: Cast
) -> None:
    busy = _make(service, cast, "Busy")
    idle = _make(service, cast, "Idle")
    for status in (TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.DONE):
        tasks.create_task(
            cast.team.id,
            TaskCreate(title=f"Busy {status}", status=status, project_id=busy.id),
            actor=cast.owner,
        )
    tasks.create_task(cast.team.id, TaskCreate(title="Loose"), actor=cast.owner)

    rows, _, _ = service.list_projects(cast.team.id, actor=cast.owner)
    counts = {project.id: count for project, count in rows}

    assert (counts[busy.id].total, counts[busy.id].open) == (3, 2)
    assert (counts[idle.id].total, counts[idle.id].open) == (0, 0)


# --- names -----------------------------------------------------------------
@pytest.mark.parametrize("taken", ["Website", "website", "WEBSITE", "  Website "])
def test_names_are_unique_per_workspace_regardless_of_case(
    service: ProjectService, cast: Cast, taken: str
) -> None:
    _make(service, cast, "Website")

    with pytest.raises(ProjectNameInUseError):
        _make(service, cast, taken)


def test_case_folding_is_unicode_aware_on_every_database(
    service: ProjectService, cast: Cast
) -> None:
    """SQLite's lower() would miss both of these; the stored key does not."""
    _make(service, cast, "Ärger")
    _make(service, cast, "Straße")

    with pytest.raises(ProjectNameInUseError):
        _make(service, cast, "ärger")
    with pytest.raises(ProjectNameInUseError):
        _make(service, cast, "STRASSE")


def test_the_same_name_is_fine_in_another_workspace(service: ProjectService, cast: Cast) -> None:
    _make(service, cast, "Website")

    other = service.create_project(
        cast.elsewhere.id, ProjectCreate(name="Website"), actor=cast.outsider
    )

    assert other.workspace_id == cast.elsewhere.id


def test_the_database_settles_a_race_for_the_same_name(
    service: ProjectService, cast: Cast, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two creates that both pass the friendly check: the constraint refuses one."""
    _make(service, cast, "Launch")
    monkeypatch.setattr(project_repository, "name_taken", lambda *args, **kwargs: False)

    with pytest.raises(ProjectNameInUseError):
        _make(service, cast, "LAUNCH")

    # The failed insert was rolled back; the session is usable and nothing leaked.
    rows, total, _ = service.list_projects(cast.team.id, actor=cast.owner)
    assert total == 1 and rows[0][0].name == "Launch"


def test_renaming_onto_another_projects_name_is_refused(
    service: ProjectService, cast: Cast
) -> None:
    _make(service, cast, "Website")
    app = _make(service, cast, "App")

    with pytest.raises(ProjectNameInUseError):
        service.update_project(app.id, ProjectUpdate(name="WEBSITE"), actor=cast.manager)


def test_a_project_may_change_the_case_of_its_own_name(
    service: ProjectService, cast: Cast
) -> None:
    project = _make(service, cast, "website")

    renamed = service.update_project(
        project.id, ProjectUpdate(name="Website"), actor=cast.manager
    )

    assert renamed.name == "Website"
    assert renamed.name_key == "website"
    assert renamed.version == 2


# --- updating --------------------------------------------------------------
def test_update_only_touches_supplied_fields_and_null_clears_description(
    service: ProjectService, cast: Cast
) -> None:
    project = service.create_project(
        cast.team.id, ProjectCreate(name="Docs", description="All of them"), actor=cast.owner
    )

    renamed = service.update_project(
        project.id, ProjectUpdate(name="Handbook"), actor=cast.owner
    )
    assert (renamed.name, renamed.description) == ("Handbook", "All of them")

    cleared = service.update_project(
        project.id, ProjectUpdate(description=None), actor=cast.owner
    )
    assert (cleared.name, cleared.description) == ("Handbook", None)


def test_a_stale_version_is_a_conflict(service: ProjectService, cast: Cast) -> None:
    project = _make(service, cast, "Contested")
    seen = project.version
    service.update_project(project.id, ProjectUpdate(name="First"), actor=cast.manager)

    with pytest.raises(ProjectConflictError):
        service.update_project(
            project.id, ProjectUpdate(name="Second", version=seen), actor=cast.owner
        )
    with pytest.raises(ProjectConflictError):
        service.delete_project(project.id, actor=cast.owner, version=seen)

    assert service.get_project(project.id, actor=cast.owner).name == "First"


# --- deleting --------------------------------------------------------------
def test_managers_cannot_delete_but_owners_and_admins_can(
    service: ProjectService, cast: Cast
) -> None:
    """Deleting reorganizes everyone's work at once: a manager shapes, never deletes."""
    by_admin = _make(service, cast, "Admin's to delete")
    by_owner = _make(service, cast, "Owner's to delete")

    with pytest.raises(WorkspaceRoleNotAllowedError):
        service.delete_project(by_admin.id, actor=cast.manager)

    service.delete_project(by_admin.id, actor=cast.admin)
    service.delete_project(by_owner.id, actor=cast.owner)

    _, total, _ = service.list_projects(cast.team.id, actor=cast.owner)
    assert total == 0


def test_deleting_a_project_keeps_its_tasks_without_a_project(
    service: ProjectService, tasks: TaskService, cast: Cast, session: Session
) -> None:
    doomed = _make(service, cast, "Doomed")
    kept = _make(service, cast, "Kept")
    inside = tasks.create_task(
        cast.team.id, TaskCreate(title="Inside", project_id=doomed.id), actor=cast.member
    )
    elsewhere = tasks.create_task(
        cast.team.id, TaskCreate(title="Elsewhere", project_id=kept.id), actor=cast.member
    )
    before = inside.version

    service.delete_project(doomed.id, actor=cast.admin)

    survivor = session.get(Task, inside.id)
    assert survivor is not None
    assert survivor.project_id is None
    assert survivor.project is None
    # Recorded like any other save: a new version, by whoever deleted the project.
    assert survivor.version == before + 1
    assert survivor.updated_by_id == cast.admin.id
    assert tasks.get_task(elsewhere.id, actor=cast.owner).project_id == kept.id
    assert session.get(Project, doomed.id) is None


def test_an_editor_holding_the_old_version_gets_a_conflict_after_detach(
    service: ProjectService, tasks: TaskService, cast: Cast
) -> None:
    """A stale save must not write a deleted project's id back onto a task."""
    doomed = _make(service, cast, "Going away")
    task = tasks.create_task(
        cast.team.id, TaskCreate(title="Open in a tab", project_id=doomed.id), actor=cast.owner
    )
    seen = task.version

    service.delete_project(doomed.id, actor=cast.owner)

    with pytest.raises(TaskConflictError):
        tasks.update_task(task.id, TaskUpdate(title="Stale", version=seen), actor=cast.manager)


# --- view mode -------------------------------------------------------------
def test_a_suspended_company_keeps_its_projects_readable_and_frozen(
    service: ProjectService, cast: Cast
) -> None:
    project = _make(service, cast, "Frozen")
    cast.workspaces.set_suspended(cast.team.id, suspended=True, note=None)

    assert service.get_project(project.id, actor=cast.member).name == "Frozen"
    assert service.list_projects(cast.team.id, actor=cast.member)[1] == 1
    for attempt in (
        lambda: _make(service, cast, "New", actor=cast.manager),
        lambda: service.update_project(
            project.id, ProjectUpdate(name="Thaw"), actor=cast.owner
        ),
        lambda: service.delete_project(project.id, actor=cast.owner),
    ):
        with pytest.raises(WorkspaceSuspendedError):
            attempt()


def test_a_private_workspace_has_projects_too(
    service: ProjectService, tasks: TaskService, cast: Cast
) -> None:
    private = tasks.personal_workspace_id(actor=cast.member)

    project = service.create_project(private, ProjectCreate(name="Errands"), actor=cast.member)
    service.delete_project(project.id, actor=cast.member)

    with pytest.raises(ProjectNotFoundError):
        service.get_project(project.id, actor=cast.member)
