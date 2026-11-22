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

Changing or deleting one task adds a rule about that task (``permissions``):
owners, admins and managers may change or delete any task, a member only the
ones they created (change, delete) or are assigned to (change), and a viewer
none. A member told no by that rule gets ``403 TASK_FORBIDDEN``; everything else
--- a viewer, a suspended company, an outsider --- is refused by the policy
first, in its own shape. Every task the API returns carries what its caller may
do to it (``task_capabilities``), computed by the same function.

A task may be assigned only to a member of its own workspace. The policy answers
that too (``members_among``), so "who can hold work here" and "who can see it"
can never drift apart; a departing member's assignments are released by
``tasks.membership`` in the workspaces module's own transaction. A task's project
must likewise be one of its own workspace's projects, which the projects module
states (``projects.references``), and each of its labels one of its own
workspace's labels, which the labels module states (``labels.references``).

Every change is written to the activity log *in the same transaction*: created,
updated (one event per save, with each changed field's before and after) and
deleted. The event is recorded after the flush --- so it carries the version the
save produced --- and before the commit, so a save refused with ``409`` or
``403``, or lost to a concurrent save at flush, leaves no event behind, and a
committed save is never missing one. A "keep mine" save after a conflict is an
ordinary update: its ``from`` values are exactly what it overwrote.

People are told in the same transaction too (``notifications.Notifier``): the
creator starts watching a new task, and a new assignee watches it and --- unless
they assigned themselves --- gets a notification. Marking a task done tells the
assignees of the tasks it was the last open blocker of that they are ready to
start (``task_dependencies.blockers``), and runs the workspace's automation rules
for a finished task (``automations.runner``) --- all in the same transaction.

A bulk request --- one set of changes, or a delete, for up to a page of tasks of
one workspace --- is the same save, once per task, in one transaction: every task
is checked by the same rule, recorded with its own event, and tells the same
people, exactly as if it had been saved alone. It is all or nothing. A refusal
names every task that caused it, in the order the checks run for a single save:
not found, then not the caller's to change, then changed since it was read.

Shared editing is guarded by optimistic concurrency: a caller that sends the
``version`` it read gets ``TaskConflictError`` (409) instead of silently undoing
a colleague's newer change. The database enforces the same check on every write
through SQLAlchemy's ``version_id_col``, so two saves racing each other cannot
both succeed either. Labels live in a link table, which that column does not
watch, so a save that changes only a task's labels stamps ``updated_at`` itself:
the version still moves, and the write is still checked.
"""

import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.modules.activity.enums import ActivityVerb
from app.modules.activity.recorder import ActivityRecorder
from app.modules.automations import runner as automations
from app.modules.labels.models import Label
from app.modules.labels.references import labels_in_workspace
from app.modules.notifications.notifier import Notifier
from app.modules.projects.models import Project
from app.modules.projects.references import project_in_workspace
from app.modules.task_dependencies import blockers
from app.modules.tasks import history, permissions, repository
from app.modules.tasks.enums import (
    AssigneeScope,
    LabelScope,
    ProjectScope,
    StatusScope,
    TaskAction,
    TaskOrder,
    TaskPriority,
    TaskStatus,
)
from app.modules.tasks.exceptions import (
    AssigneeNotMemberError,
    BulkTaskConflictError,
    BulkTaskForbiddenError,
    LabelNotInWorkspaceError,
    ProjectNotInWorkspaceError,
    TaskConflictError,
    TaskLabelLimitError,
    TaskNotFoundError,
)
from app.modules.tasks.models import Task
from app.modules.tasks.schemas import (
    MAX_LABELS_PER_TASK,
    BulkTaskChanges,
    BulkTaskDelete,
    BulkTaskRef,
    BulkTaskUpdate,
    TaskCreate,
    TaskUpdate,
)
from app.modules.users.models import User
from app.modules.workspaces.access import WorkspaceAccess, WorkspaceAccessPolicy
from app.modules.workspaces.enums import WorkspaceAction, WorkspaceKind
from app.shared.time import utc_now


class TaskService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._access = WorkspaceAccessPolicy(session)
        self._recorder = ActivityRecorder(session)
        self._notifier = Notifier(session)

    # --- collections (addressed by workspace) -------------------------------
    def create_task(self, workspace_id: uuid.UUID, data: TaskCreate, *, actor: User) -> Task:
        access = self._access.require(
            workspace_id, actor=actor, action=WorkspaceAction.EDIT_CONTENT
        )
        task = Task(
            **data.model_dump(exclude={"assignee_id", "project_id", "label_ids"}),
            workspace_id=access.workspace.id,
            created_by=actor,
            assignee=self._assignee(access.workspace.id, data.assignee_id),
            project=self._project(access.workspace.id, data.project_id),
            labels=self._labels(access.workspace.id, data.label_ids),
        )
        repository.add_task(self._session, task)

        def record_creation() -> None:
            self._record(
                ActivityVerb.TASK_CREATED, task, actor=actor, changes=history.initial(task)
            )
            self._notifier.watch(task, [actor])
            if task.assignee is not None:
                self._notifier.task_assigned(task, assignee=task.assignee, actor=actor)

        self._write(task.id, then=record_creation)
        return task

    def list_tasks(
        self,
        workspace_id: uuid.UUID,
        *,
        actor: User,
        status: TaskStatus | StatusScope | None = None,
        priority: TaskPriority | None = None,
        assignee: uuid.UUID | AssigneeScope | None = None,
        project: uuid.UUID | ProjectScope | None = None,
        label: uuid.UUID | LabelScope | None = None,
        due_from: date | None = None,
        due_to: date | None = None,
        has_due_date: bool | None = None,
        search: str | None = None,
        order: TaskOrder = TaskOrder.NEWEST,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[Task], int]:
        """One page of a tenant's tasks.

        ``status`` is one status or ``open`` (anything not done); ``assignee`` is
        a member's id, ``me`` (the caller) or ``none`` (nobody); ``project`` is a
        project's id or ``none``, and ``label`` a label's id or ``none`` (tasks
        carrying no label). ``due_from`` and ``due_to`` bound the due date, both
        inclusive. An id from elsewhere simply matches nothing: the filters read
        this tenant only, so they cannot be used to learn about anyone or anything
        in another workspace.
        """
        access = self._access.require(workspace_id, actor=actor, action=WorkspaceAction.READ)
        return repository.list_tasks(
            self._session,
            workspace_id=access.workspace.id,
            filters=_filters(
                status=status,
                priority=priority,
                assignee_id=actor.id if assignee is AssigneeScope.ME else _as_id(assignee),
                unassigned=assignee is AssigneeScope.NONE,
                project=project,
                label=label,
                due_from=due_from,
                due_to=due_to,
                has_due_date=has_due_date,
                search=search,
            ),
            order=order,
            page=page,
            page_size=page_size,
        )

    def list_my_tasks(
        self,
        *,
        actor: User,
        workspace: uuid.UUID | None = None,
        status: TaskStatus | StatusScope | None = None,
        priority: TaskPriority | None = None,
        project: uuid.UUID | ProjectScope | None = None,
        label: uuid.UUID | LabelScope | None = None,
        due_from: date | None = None,
        due_to: date | None = None,
        has_due_date: bool | None = None,
        search: str | None = None,
        order: TaskOrder = TaskOrder.DUE,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[Task], int]:
        """One page of the caller's own work, across every tenant they may read.

        Their own work is what is assigned to them anywhere, plus the unassigned
        tasks of their private workspace. Which tenants count is the access
        policy's answer (``readable``), so leaving a company takes its tasks off
        this list at once, and a suspended company's stay readable here as they
        do on its board. ``workspace`` narrows it to one of those tenants; an id
        the caller cannot read matches nothing rather than raising, so the filter
        never confirms that a tenant exists.
        """
        scope = self.my_scope(actor=actor)
        workspace_ids = {access.workspace.id for access in scope.accesses}
        if workspace is not None:
            workspace_ids &= {workspace}
        return repository.list_assigned(
            self._session,
            user_id=actor.id,
            workspace_ids=workspace_ids,
            personal_workspace_id=scope.personal_workspace_id,
            filters=_filters(
                status=status,
                priority=priority,
                project=project,
                label=label,
                due_from=due_from,
                due_to=due_to,
                has_due_date=has_due_date,
                search=search,
            ),
            order=order,
            page=page,
            page_size=page_size,
        )

    def my_scope(self, *, actor: User) -> "MyScope":
        """Where the caller's own work lives: every tenant they may read now, and
        which of them is their private one.

        The one definition behind their list (:meth:`list_my_tasks`) and their
        dashboard's counts, so the two always describe the same tasks.
        """
        accesses = self._access.readable(actor=actor)
        personal = next(
            (
                access.workspace.id
                for access in accesses
                if access.workspace.kind is WorkspaceKind.PERSONAL
            ),
            None,
        )
        return MyScope(accesses=accesses, personal_workspace_id=personal)

    def task_capabilities(
        self, tasks: Sequence[Task], *, actor: User
    ) -> Mapping[uuid.UUID, list[TaskAction]]:
        """What the caller may do to each of ``tasks``, for the API's ``capabilities``.

        For tasks the caller was already authorized to read. One membership read
        for a whole page, even one spanning several workspaces (``/me/tasks``); a
        task in a workspace the caller cannot read --- which no route returns ---
        would simply be given no actions.
        """
        accesses = {access.workspace.id: access for access in self._access.readable(actor=actor)}
        return {
            task.id: (
                permissions.allowed_actions(
                    task, access=accesses[task.workspace_id], actor_id=actor.id
                )
                if task.workspace_id in accesses
                else []
            )
            for task in tasks
        }

    def open_blocker_counts(self, tasks: Sequence[Task]) -> Mapping[uuid.UUID, int]:
        """How many unfinished tasks each of ``tasks`` still waits on.

        For tasks the caller was already authorized to read; one grouped query for
        a whole page.
        """
        return blockers.open_blocker_counts(self._session, [task.id for task in tasks])

    def personal_workspace_id(self, *, actor: User) -> uuid.UUID:
        """The caller's private tenant, for the ``/tasks`` shortcut routes."""
        return self._access.require_personal(actor=actor).workspace.id

    # --- single tasks (addressed by id) -------------------------------------
    def get_task(self, task_id: uuid.UUID, *, actor: User) -> Task:
        return self.authorized_task(task_id, actor=actor, action=WorkspaceAction.READ)

    def update_task(self, task_id: uuid.UUID, data: TaskUpdate, *, actor: User) -> Task:
        task = self.changeable_task(task_id, actor=actor, action=TaskAction.EDIT)
        self._check_version(task, data.version)
        changes = data.model_dump(exclude_unset=True, exclude={"version"})
        if not changes:
            return task
        edit = self._edit(task.workspace_id, changes)
        before = self._apply(task, edit, actor=actor)
        self._write(task_id, then=lambda: self._after_updates([(task, before)], actor=actor))
        return task

    def delete_task(self, task_id: uuid.UUID, *, actor: User, version: int | None = None) -> None:
        """Delete, optionally only if nobody changed the task since ``version``.

        The ``task.deleted`` event keeps the task's id and title, so the
        workspace's feed can still say what was deleted after the row is gone.
        """
        task = self.changeable_task(task_id, actor=actor, action=TaskAction.DELETE)
        self._check_version(task, version)
        workspace_id, title, last_version = task.workspace_id, task.title, task.version
        repository.delete_task(self._session, task)

        def record_deletion() -> None:
            self._recorder.record(
                ActivityVerb.TASK_DELETED,
                workspace_id=workspace_id,
                actor=actor,
                task_id=task_id,
                task_title=title,
                task_version=last_version,
            )

        self._write(task_id, then=record_deletion)

    # --- several tasks at once (addressed by workspace) ----------------------
    def bulk_update(
        self, workspace_id: uuid.UUID, data: BulkTaskUpdate, *, actor: User
    ) -> list[Task]:
        """Apply one set of changes to every named task, all or nothing.

        Each task is saved exactly as :meth:`update_task` would save it --- same
        rule, same event, same notifications, same "ready to start" --- in one
        transaction. Returned in the order the request named them.
        """
        access, tasks = self._bulk_targets(workspace_id, data.tasks, TaskAction.EDIT, actor=actor)
        edit = self._bulk_edit(access.workspace.id, data.changes)
        if edit.labels is not None:
            relabel = edit.labels
            over = [i for i, task in enumerate(tasks) if len(relabel(task)) > MAX_LABELS_PER_TASK]
            if over:
                raise TaskLabelLimitError(over)
        saved = [(task, self._apply(task, edit, actor=actor)) for task in tasks]
        self._flush_and_commit(
            BulkTaskConflictError(), then=lambda: self._after_updates(saved, actor=actor)
        )
        return tasks

    def bulk_delete(self, workspace_id: uuid.UUID, data: BulkTaskDelete, *, actor: User) -> None:
        """Delete every named task, all or nothing, each with its own ``task.deleted``."""
        _access, tasks = self._bulk_targets(
            workspace_id, data.tasks, TaskAction.DELETE, actor=actor
        )
        gone = [(task.id, task.workspace_id, task.title, task.version) for task in tasks]
        for task in tasks:
            repository.delete_task(self._session, task)

        def record_deletions() -> None:
            for task_id, in_workspace, title, last_version in gone:
                self._recorder.record(
                    ActivityVerb.TASK_DELETED,
                    workspace_id=in_workspace,
                    actor=actor,
                    task_id=task_id,
                    task_title=title,
                    task_version=last_version,
                )

        self._flush_and_commit(BulkTaskConflictError(), then=record_deletions)

    def _bulk_targets(
        self,
        workspace_id: uuid.UUID,
        refs: Sequence[BulkTaskRef],
        action: TaskAction,
        *,
        actor: User,
    ) -> tuple[WorkspaceAccess, list[Task]]:
        """The tasks a bulk request names, in its order, once every one may be ``action``-ed.

        The same checks as a single save, in the same order, for the whole
        selection before anything is written: the workspace (not found for an
        outsider, the policy's 403 for a viewer or a suspended company); each task
        is in it (not found, like any missing task); each is the caller's to change
        (403 naming every one that is not); each is still at the version the
        client read (409 naming every stale one).
        """
        access = self._access.require(
            workspace_id, actor=actor, action=WorkspaceAction.EDIT_CONTENT
        )
        found = repository.get_tasks_in_workspace(
            self._session, access.workspace.id, [ref.id for ref in refs]
        )
        missing = next((ref.id for ref in refs if ref.id not in found), None)
        if missing is not None:
            raise TaskNotFoundError(missing)
        tasks = [found[ref.id] for ref in refs]
        forbidden = [
            index
            for index, task in enumerate(tasks)
            if not permissions.is_allowed(action, task, access=access, actor_id=actor.id)
        ]
        if forbidden:
            raise BulkTaskForbiddenError(forbidden)
        stale = [
            index
            for index, (ref, task) in enumerate(zip(refs, tasks, strict=True))
            if ref.version is not None and ref.version != task.version
        ]
        if stale:
            raise BulkTaskConflictError(stale)
        return access, tasks

    # --- for content that lives on a task (comments, activity) --------------
    def authorized_task(self, task_id: uuid.UUID, *, actor: User, action: WorkspaceAction) -> Task:
        """The task, once the policy allows ``action`` in the workspace holding it.

        Missing task and "in a workspace you are not in" both raise
        ``TaskNotFoundError`` with the same payload. Public so that what lives on
        a task --- its comments, its history --- is reached through exactly the
        same rule as the task itself.
        """
        task, _access = self._authorized(task_id, actor=actor, action=action)
        return task

    def changeable_task(self, task_id: uuid.UUID, *, actor: User, action: TaskAction) -> Task:
        """The task, once the caller may ``action`` it: the workspace's rule, then its own.

        Outsiders get ``TaskNotFoundError``; a viewer or a suspended company the
        policy's 403; a member reaching for someone else's task
        ``TaskForbiddenError``. Public so that what changes a task from outside
        this module --- its blockers --- is held to exactly the same rule.
        """
        task, access = self._authorized(task_id, actor=actor, action=WorkspaceAction.READ)
        permissions.enforce(action, task, access=access, actor_id=actor.id)
        return task

    def _authorized(
        self, task_id: uuid.UUID, *, actor: User, action: WorkspaceAction
    ) -> tuple[Task, WorkspaceAccess]:
        """The task and the caller's access to its workspace, once ``action`` is allowed."""
        task = repository.get_task(self._session, task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        access = self._access.require_for_content(
            task.workspace_id,
            actor=actor,
            action=action,
            hidden_as=TaskNotFoundError(task_id),
        )
        return task, access

    def _assignee(self, workspace_id: uuid.UUID, user_id: uuid.UUID | None) -> User | None:
        """The account to assign, once it is known to be a member of the tenant.

        Only called after the caller's own access to ``workspace_id`` was
        authorized, so the answer concerns the tenant the caller already sees.
        """
        if user_id is None:
            return None
        account = self._access.members_among(workspace_id, {user_id}).get(user_id)
        if account is None:
            raise AssigneeNotMemberError(user_id)
        return account

    def _project(self, workspace_id: uuid.UUID, project_id: uuid.UUID | None) -> Project | None:
        """The project to file under, once it is known to be in the same tenant."""
        if project_id is None:
            return None
        project = project_in_workspace(self._session, workspace_id, project_id)
        if project is None:
            raise ProjectNotInWorkspaceError(project_id)
        return project

    def _labels(self, workspace_id: uuid.UUID, label_ids: Sequence[uuid.UUID]) -> list[Label]:
        """The labels to carry, once each is known to be in the same tenant.

        Alphabetical, as the task will list them after any reload.
        """
        if not label_ids:
            return []
        found = labels_in_workspace(self._session, workspace_id, label_ids)
        for label_id in label_ids:
            if label_id not in found:
                raise LabelNotInWorkspaceError(label_id)
        return sorted(found.values(), key=lambda label: (label.name_key, str(label.id)))

    # --- applying a change -----------------------------------------------------
    def _edit(self, workspace_id: uuid.UUID, changes: dict[str, Any]) -> "_Edit":
        """A single save's fields, with its assignee, project and labels resolved."""
        edit = _Edit(columns={})
        if "assignee_id" in changes:
            edit = replace(
                edit,
                has_assignee=True,
                assignee=self._assignee(workspace_id, changes.pop("assignee_id")),
            )
        if "project_id" in changes:
            edit = replace(
                edit,
                has_project=True,
                project=self._project(workspace_id, changes.pop("project_id")),
            )
        if "label_ids" in changes:
            chosen = self._labels(workspace_id, changes.pop("label_ids"))
            edit = replace(edit, labels=lambda _task: chosen)
        return replace(edit, columns=changes)

    def _bulk_edit(self, workspace_id: uuid.UUID, changes: BulkTaskChanges) -> "_Edit":
        """A bulk request's changes, resolved once for every task they apply to.

        Labels are added and removed per task: each keeps the labels it had that
        are not removed, plus the added ones it did not have yet.
        """
        edit = self._edit(
            workspace_id,
            changes.model_dump(exclude_unset=True, exclude={"add_label_ids", "remove_label_ids"}),
        )
        added = self._labels(workspace_id, changes.add_label_ids)
        removed = {label.id for label in self._labels(workspace_id, changes.remove_label_ids)}
        if not added and not removed:
            return edit

        def relabel(task: Task) -> list[Label]:
            kept = [label for label in task.labels if label.id not in removed]
            carried = {label.id for label in kept}
            merged = [*kept, *(label for label in added if label.id not in carried)]
            return sorted(merged, key=lambda label: (label.name_key, str(label.id)))

        return replace(edit, labels=relabel)

    def _apply(self, task: Task, edit: "_Edit", *, actor: User) -> dict[str, Any]:
        """Make ``edit`` on ``task`` in memory; return what the task was before."""
        before = history.snapshot(task)
        if edit.has_assignee:
            # Through the relationship, not the column: the loaded ``assignee``
            # would otherwise answer with the previous person until reloaded.
            task.assignee = edit.assignee
        if edit.has_project:
            task.project = edit.project
        if edit.labels is not None:
            labels = edit.labels(task)
            if {label.id for label in labels} != {label.id for label in task.labels}:
                task.labels = labels
                # The link table is invisible to the version column: touch the row
                # so this save is versioned and conflict-checked like any other.
                task.updated_at = utc_now()
        for field, value in edit.columns.items():
            setattr(task, field, value)
        task.updated_by = actor
        return before

    def _after_updates(
        self, saved: Sequence[tuple[Task, dict[str, Any]]], *, actor: User
    ) -> None:
        """Record and announce saved tasks (each with what it was before), after the
        flush and before the commit.

        Tasks finished together are announced together, so a task they unblock is
        "ready to start" once, however many of its blockers were in the save.
        """
        finished: list[Task] = []
        for task, before in saved:
            # Saving a value a field already had changes nothing, and says nothing.
            changed = history.diff(before, history.snapshot(task))
            if changed:
                self._record(ActivityVerb.TASK_UPDATED, task, actor=actor, changes=changed)
            if "assignee" in changed and task.assignee is not None:
                self._notifier.task_assigned(task, assignee=task.assignee, actor=actor)
            if "status" in changed and task.status is TaskStatus.DONE:
                finished.append(task)
        if finished:
            blockers.tasks_finished(self._session, finished, actor=actor)
            automations.tasks_completed(self._session, finished, actor=actor)

    # --- helpers -----------------------------------------------------------
    def _record(
        self,
        verb: ActivityVerb,
        task: Task,
        *,
        actor: User,
        changes: dict[str, Any],
    ) -> None:
        """One event about ``task`` as it is now, in this transaction."""
        self._recorder.record(
            verb,
            workspace_id=task.workspace_id,
            actor=actor,
            task_id=task.id,
            task_title=task.title,
            task_version=task.version,
            changes=changes,
        )

    @staticmethod
    def _check_version(task: Task, expected: int | None) -> None:
        if expected is not None and expected != task.version:
            raise TaskConflictError(task.id)

    def _write(self, task_id: uuid.UUID, *, then: Callable[[], None] | None = None) -> None:
        """Flush, run ``then``, commit; a lost optimistic-lock race becomes a 409."""
        self._flush_and_commit(TaskConflictError(task_id), then=then)

    def _flush_and_commit(
        self, conflict: Exception, *, then: Callable[[], None] | None = None
    ) -> None:
        """Flush, run ``then``, commit; a lost optimistic-lock race raises ``conflict``.

        ``then`` records the activity event: after the flush (so the new version
        is known and a lost race never reaches it) and before the commit (so the
        event and the change are one transaction). If recording fails, the change
        is rolled back with it --- a change is never committed without its event.
        """
        try:
            self._session.flush()
        except StaleDataError:
            self._session.rollback()
            raise conflict from None
        try:
            if then is not None:
                then()
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise


@dataclass(frozen=True)
class MyScope:
    """The tenants a person's own work is read from, personal one first."""

    accesses: Sequence[WorkspaceAccess]
    personal_workspace_id: uuid.UUID | None


@dataclass(frozen=True)
class _Edit:
    """One change, resolved against its workspace once, ready for any of its tasks.

    ``columns`` are set as given. The assignee and project are applied through
    their relationships, and only when ``has_*`` says they change --- ``None`` is a
    real value for both (nobody, no project). ``labels`` gives each task its new
    set from its current one, so "add Bug" on a selection keeps every task's other
    labels; ``None`` leaves labels alone.
    """

    columns: Mapping[str, Any]
    has_assignee: bool = False
    assignee: User | None = None
    has_project: bool = False
    project: Project | None = None
    labels: Callable[[Task], list[Label]] | None = None


def _filters(
    *,
    status: TaskStatus | StatusScope | None,
    priority: TaskPriority | None,
    assignee_id: uuid.UUID | None = None,
    unassigned: bool = False,
    project: uuid.UUID | ProjectScope | None,
    label: uuid.UUID | LabelScope | None,
    due_from: date | None,
    due_to: date | None,
    has_due_date: bool | None,
    search: str | None,
) -> repository.TaskFilters:
    """The repository's filters for what a caller asked, with named scopes resolved."""
    return repository.TaskFilters(
        status=status if isinstance(status, TaskStatus) else None,
        open_only=status is StatusScope.OPEN,
        priority=priority,
        assignee_id=assignee_id,
        unassigned=unassigned,
        project_id=_as_id(project),
        without_project=project is ProjectScope.NONE,
        label_id=_as_id(label),
        without_labels=label is LabelScope.NONE,
        due_from=due_from,
        due_to=due_to,
        has_due_date=has_due_date,
        search=search,
    )


def _as_id(
    value: uuid.UUID | AssigneeScope | ProjectScope | LabelScope | None,
) -> uuid.UUID | None:
    """The id in an assignee, project or label filter, or ``None`` for the named scopes."""
    return value if isinstance(value, uuid.UUID) else None
