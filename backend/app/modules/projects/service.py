"""Application service implementing project use cases.

Business rules live here, not in route handlers. Transaction boundaries are
committed at this use-case layer and rolled back on failure
(architecture doc section 6.2).

Whether the acting user may touch a workspace's projects is decided by
``workspaces.access.WorkspaceAccessPolicy`` --- never here. This service only
names the action it is attempting:

==============================  ======================  ==============================
Use case                        Action                  Who, in an active tenant
==============================  ======================  ==============================
List and read projects          ``read``                every member
Create, rename, describe        ``manage_projects``     owners, admins and managers
Delete                          ``manage``              owners and admins
==============================  ======================  ==============================

Members file their tasks under projects --- that is editing the task --- but
shaping the set of projects everyone files under is for the people running the
work. Viewers read.

Deleting is ``manage`` because it reorganizes everyone's work at once: every
task in the project is taken out of it. Nothing is lost --- the tasks stay in the
workspace, detached in this same transaction by the tasks module --- but it is
the kind of change a company expects its owners and admins to make. A suspended
company is in view mode, so only reads succeed there, and a project in a
workspace the caller is not in reads as not found, exactly like one that does not
exist (architecture doc sections 7 and 9).

Renames from two people at once are guarded by optimistic concurrency, as on
tasks: a stale ``version`` answers ``409 PROJECT_CONFLICT``.
"""

import math
import uuid
from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.modules.projects import repository
from app.modules.projects.exceptions import (
    ProjectConflictError,
    ProjectNameInUseError,
    ProjectNotFoundError,
)
from app.modules.projects.models import Project
from app.modules.projects.schemas import ProjectCreate, ProjectUpdate
from app.modules.tasks.project_links import ProjectTaskCounts, count_by_project, detach_project
from app.modules.users.models import User
from app.modules.workspaces.access import WorkspaceAccessPolicy
from app.modules.workspaces.enums import WorkspaceAction


class ProjectService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._access = WorkspaceAccessPolicy(session)

    # --- collections (addressed by workspace) -------------------------------
    def create_project(
        self, workspace_id: uuid.UUID, data: ProjectCreate, *, actor: User
    ) -> Project:
        access = self._access.require(
            workspace_id, actor=actor, action=WorkspaceAction.MANAGE_PROJECTS
        )
        if repository.name_taken(self._session, access.workspace.id, data.name):
            raise ProjectNameInUseError
        project = Project(**data.model_dump(), workspace_id=access.workspace.id, created_by=actor)
        try:
            repository.add_project(self._session, project)
        except IntegrityError:
            # Someone created the same name between the check and the insert.
            self._session.rollback()
            raise ProjectNameInUseError from None
        self._commit()
        return project

    def list_projects(
        self,
        workspace_id: uuid.UUID,
        *,
        actor: User,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[tuple[Project, ProjectTaskCounts]], int, int]:
        """One page of a tenant's projects, each with how much work it holds."""
        access = self._access.require(workspace_id, actor=actor, action=WorkspaceAction.READ)
        projects, total = repository.list_projects(
            self._session, workspace_id=access.workspace.id, page=page, page_size=page_size
        )
        counts = count_by_project(self._session, [project.id for project in projects])
        rows = [(project, counts[project.id]) for project in projects]
        return rows, total, _pages(total, page, page_size)

    # --- single projects (addressed by id) ----------------------------------
    def get_project(self, project_id: uuid.UUID, *, actor: User) -> Project:
        return self._authorized_project(project_id, actor=actor, action=WorkspaceAction.READ)

    def update_project(
        self, project_id: uuid.UUID, data: ProjectUpdate, *, actor: User
    ) -> Project:
        project = self._authorized_project(
            project_id, actor=actor, action=WorkspaceAction.MANAGE_PROJECTS
        )
        self._check_version(project, data.version)
        changes = data.model_dump(exclude_unset=True, exclude={"version"})
        if not changes:
            return project
        name = changes.get("name")
        if name is not None and repository.name_taken(
            self._session, project.workspace_id, name, excluding=project.id
        ):
            raise ProjectNameInUseError
        for field, value in changes.items():
            setattr(project, field, value)
        self._write(project_id)
        return project

    def delete_project(
        self, project_id: uuid.UUID, *, actor: User, version: int | None = None
    ) -> None:
        """Delete a project and take its tasks out of it, in one transaction.

        Optionally only if nobody changed the project since ``version``.
        """
        project = self._authorized_project(project_id, actor=actor, action=WorkspaceAction.MANAGE)
        self._check_version(project, version)
        detach_project(self._session, project=project, actor=actor)
        repository.delete_project(self._session, project)
        self._write(project_id)

    # --- helpers -----------------------------------------------------------
    def _authorized_project(
        self, project_id: uuid.UUID, *, actor: User, action: WorkspaceAction
    ) -> Project:
        """The project, once the policy allows ``action`` in the workspace holding it.

        Missing project and "in a workspace you are not in" both raise
        ``ProjectNotFoundError`` with the same payload.
        """
        project = repository.get_project(self._session, project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        self._access.require_for_content(
            project.workspace_id,
            actor=actor,
            action=action,
            hidden_as=ProjectNotFoundError(project_id),
        )
        return project

    @staticmethod
    def _check_version(project: Project, expected: int | None) -> None:
        if expected is not None and expected != project.version:
            raise ProjectConflictError(project.id)

    def _write(self, project_id: uuid.UUID) -> None:
        """Flush and commit; a lost race becomes a 409 of the matching kind."""
        try:
            self._session.flush()
        except StaleDataError:
            self._session.rollback()
            raise ProjectConflictError(project_id) from None
        except IntegrityError:
            # Only the case-insensitive name index can refuse a project write.
            self._session.rollback()
            raise ProjectNameInUseError from None
        self._commit()

    def _commit(self) -> None:
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise


def _pages(total: int, page: int, page_size: int) -> int:
    """Page count for the collection envelope."""
    return math.ceil(total / page_size) if total else 0
