"""Who may change or delete one task: the workspace's rule, then the task's own.

``workspaces.access`` decides what a *role* allows in a tenant. A task adds one
rule about the *target* on top, the way a comment does ("only its author edits
it") --- and, like that rule, it lives with the content it protects:

=================  ===========================  ====================================
On one task        With ``manage_tasks``        With ``edit_content`` only
=================  ===========================  ====================================
edit               any task                     one they created or are assigned to
delete             any task                     one they created
=================  ===========================  ====================================

Owners, admins and managers hold ``manage_tasks``; members hold ``edit_content``
only; viewers hold neither, and nobody holds either in a suspended company. In a
private workspace the one member is its owner, so every task there is theirs.

The answer is computed here once and used twice --- to refuse a request
(:func:`enforce`), and to list a task's ``capabilities`` for the client
(:func:`allowed_actions`) --- so the two can never disagree. Pure functions: no
database access; the caller resolves the membership first.
"""

import uuid

from app.modules.tasks.enums import TaskAction
from app.modules.tasks.exceptions import TaskForbiddenError
from app.modules.tasks.models import Task
from app.modules.workspaces.access import WorkspaceAccess
from app.modules.workspaces.enums import WorkspaceAction


def is_allowed(
    action: TaskAction, task: Task, *, access: WorkspaceAccess, actor_id: uuid.UUID
) -> bool:
    """Whether the member behind ``access`` may perform ``action`` on ``task``.

    ``access`` must be the caller's membership of the task's own workspace.
    """
    if access.allows(WorkspaceAction.MANAGE_TASKS):
        return True
    if not access.allows(WorkspaceAction.EDIT_CONTENT):
        return False
    if action is TaskAction.DELETE:
        return task.owner_id == actor_id
    return actor_id in (task.owner_id, task.assignee_id)


def allowed_actions(
    task: Task, *, access: WorkspaceAccess, actor_id: uuid.UUID
) -> list[TaskAction]:
    """Every action the caller may perform on ``task`` now, in declaration order."""
    return [
        action
        for action in TaskAction
        if is_allowed(action, task, access=access, actor_id=actor_id)
    ]


def enforce(
    action: TaskAction, task: Task, *, access: WorkspaceAccess, actor_id: uuid.UUID
) -> None:
    """Raise the member-facing refusal if the caller may not ``action`` ``task``.

    The workspace's refusals come first, in the policy's own order --- role, then
    suspension --- so a viewer or a suspended company gets the same answer here
    as anywhere else; only then is the task's own rule checked.
    """
    access.require(WorkspaceAction.EDIT_CONTENT)
    if not is_allowed(action, task, access=access, actor_id=actor_id):
        raise TaskForbiddenError(task.id)
