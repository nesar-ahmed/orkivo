"""Application service implementing task use cases.

Business rules live here, not in route handlers. Transaction boundaries are
committed at this use-case layer and rolled back on failure
(architecture doc section 6.2).

Tasks live in a workspace, and whether the acting user may read or change them is
decided by ``workspaces.access.WorkspaceAccessPolicy`` --- never here. That gives
the product's three promises one implementation:

* members of a company create, read, edit and delete its tasks together;
* a personal workspace has one member, so its tasks stay private to its owner;
* a task in a workspace the caller is not in is reported as not found --- the
  same response as a task that does not exist, so the API never confirms that an
  id belongs to somebody else (architecture doc sections 7 and 9).

What a *suspended* company still allows (view mode: read, never write) is
likewise the policy's decision; this service only names the action it is
attempting.

Shared editing is guarded by optimistic concurrency: a caller that sends the
``version`` it read gets ``TaskConflictError`` (409) instead of silently undoing
a colleague's newer change. The database enforces the same check on every write
through SQLAlchemy's ``version_id_col``, so two saves racing each other cannot
both succeed either.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.modules.tasks import repository
from app.modules.tasks.enums import TaskPriority, TaskStatus
from app.modules.tasks.exceptions import TaskConflictError, TaskNotFoundError
from app.modules.tasks.models import Task
from app.modules.tasks.schemas import TaskCreate, TaskUpdate
from app.modules.users.models import User
from app.modules.workspaces.access import WorkspaceAccessPolicy
from app.modules.workspaces.enums import WorkspaceAction


class TaskService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._access = WorkspaceAccessPolicy(session)

    # --- collections (addressed by workspace) -------------------------------
    def create_task(self, workspace_id: uuid.UUID, data: TaskCreate, *, actor: User) -> Task:
        access = self._access.require(
            workspace_id, actor=actor, action=WorkspaceAction.EDIT_CONTENT
        )
        task = Task(**data.model_dump(), workspace_id=access.workspace.id, created_by=actor)
        repository.add_task(self._session, task)
        self._commit()
        return task

    def list_tasks(
        self,
        workspace_id: uuid.UUID,
        *,
        actor: User,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[Task], int]:
        access = self._access.require(workspace_id, actor=actor, action=WorkspaceAction.READ)
        return repository.list_tasks(
            self._session,
            workspace_id=access.workspace.id,
            status=status,
            priority=priority,
            search=search,
            page=page,
            page_size=page_size,
        )

    def personal_workspace_id(self, *, actor: User) -> uuid.UUID:
        """The caller's private tenant, for the ``/tasks`` shortcut routes."""
        return self._access.require_personal(actor=actor).workspace.id

    # --- single tasks (addressed by id) -------------------------------------
    def get_task(self, task_id: uuid.UUID, *, actor: User) -> Task:
        return self._authorized_task(task_id, actor=actor, action=WorkspaceAction.READ)

    def update_task(self, task_id: uuid.UUID, data: TaskUpdate, *, actor: User) -> Task:
        task = self._authorized_task(task_id, actor=actor, action=WorkspaceAction.EDIT_CONTENT)
        self._check_version(task, data.version)
        changes = data.model_dump(exclude_unset=True, exclude={"version"})
        if not changes:
            return task
        for field, value in changes.items():
            setattr(task, field, value)
        task.updated_by = actor
        self._write(task_id)
        return task

    def delete_task(self, task_id: uuid.UUID, *, actor: User, version: int | None = None) -> None:
        """Delete, optionally only if nobody changed the task since ``version``."""
        task = self._authorized_task(task_id, actor=actor, action=WorkspaceAction.EDIT_CONTENT)
        self._check_version(task, version)
        repository.delete_task(self._session, task)
        self._write(task_id)

    # --- helpers -----------------------------------------------------------
    def _authorized_task(self, task_id: uuid.UUID, *, actor: User, action: WorkspaceAction) -> Task:
        """The task, once the policy allows ``action`` in the workspace holding it.

        Missing task and "in a workspace you are not in" both raise
        ``TaskNotFoundError`` with the same payload.
        """
        task = repository.get_task(self._session, task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        self._access.require_for_content(
            task.workspace_id,
            actor=actor,
            action=action,
            hidden_as=TaskNotFoundError(task_id),
        )
        return task

    @staticmethod
    def _check_version(task: Task, expected: int | None) -> None:
        if expected is not None and expected != task.version:
            raise TaskConflictError(task.id)

    def _write(self, task_id: uuid.UUID) -> None:
        """Flush and commit; a lost optimistic-lock race becomes a 409."""
        try:
            self._session.flush()
        except StaleDataError:
            self._session.rollback()
            raise TaskConflictError(task_id) from None
        self._commit()

    def _commit(self) -> None:
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
