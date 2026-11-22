"""Domain/application exceptions for the tasks module."""

import uuid
from collections.abc import Sequence

from app.modules.tasks.schemas import MAX_LABELS_PER_TASK
from app.shared.errors import ErrorDetail


class TaskNotFoundError(Exception):
    """The requested task does not exist (or is not visible)."""

    code = "TASK_NOT_FOUND"
    message = "The requested task was not found."

    def __init__(self, task_id: uuid.UUID) -> None:
        super().__init__(f"Task {task_id} was not found.")
        self.task_id = task_id


class TaskForbiddenError(Exception):
    """A member tried to change or delete a task that is not theirs to change.

    The caller can read the task, so this is a 403 with the reason rather than a
    404. Only the rule about *this task* refuses here; a role that may not change
    content at all, or a suspended company, is refused first by the workspace's
    own errors.
    """

    code = "TASK_FORBIDDEN"
    message = (
        "You can change only tasks you created or are assigned to, and delete only "
        "tasks you created. Ask a manager, admin or owner."
    )

    def __init__(self, task_id: uuid.UUID) -> None:
        super().__init__(f"Task {task_id} is not the caller's to change.")
        self.task_id = task_id


class TaskConflictError(Exception):
    """Someone changed the task after the caller read it.

    Shared tasks are edited by several people; without this check the second
    save would silently undo the first. The client reloads and decides.
    """

    code = "TASK_CONFLICT"
    message = (
        "This task was changed by someone else after you opened it. "
        "Reload it to see the latest version."
    )

    def __init__(self, task_id: uuid.UUID) -> None:
        super().__init__(f"Task {task_id} changed concurrently.")
        self.task_id = task_id


class AssigneeNotMemberError(Exception):
    """The chosen assignee is not a member of the task's workspace.

    One answer for "not a member" and "no such account": the caller learns only
    that this id cannot hold work here, never whether it exists elsewhere.
    """

    code = "ASSIGNEE_NOT_MEMBER"
    message = "Tasks can only be assigned to members of their workspace."

    def __init__(self, user_id: uuid.UUID) -> None:
        super().__init__(f"User {user_id} cannot be assigned in this workspace.")
        self.user_id = user_id


class ProjectNotInWorkspaceError(Exception):
    """The chosen project is not one of the task's workspace's projects.

    One answer for "in another workspace" and "no such project", so a project id
    from elsewhere is never confirmed to exist.
    """

    code = "PROJECT_NOT_IN_WORKSPACE"
    message = "Tasks can only be filed under a project in their own workspace."

    def __init__(self, project_id: uuid.UUID) -> None:
        super().__init__(f"Project {project_id} cannot hold tasks in this workspace.")
        self.project_id = project_id


class LabelNotInWorkspaceError(Exception):
    """A chosen label is not one of the task's workspace's labels.

    One answer for "in another workspace" and "no such label", so a label id from
    elsewhere is never confirmed to exist.
    """

    code = "LABEL_NOT_IN_WORKSPACE"
    message = "Tasks can only carry labels from their own workspace."

    def __init__(self, label_id: uuid.UUID) -> None:
        super().__init__(f"Label {label_id} cannot be used in this workspace.")
        self.label_id = label_id


# --- bulk requests ---------------------------------------------------------------
# A bulk request is all or nothing, so a refusal names every task that caused it.
# Each detail points into the request body the way a validation error does ---
# ``tasks.<index>.<field>`` --- so a client maps it back to what it sent.


def _positions(indexes: Sequence[int], field: str, message: str) -> list[ErrorDetail]:
    return [ErrorDetail(field=f"tasks.{index}.{field}", message=message) for index in indexes]


class BulkTaskForbiddenError(Exception):
    """Some of the selected tasks are not the caller's to change or delete."""

    code = "TASK_FORBIDDEN"
    message = (
        "Some of the selected tasks are not yours to change. You can change only tasks you "
        "created or are assigned to, and delete only tasks you created. Nothing was changed."
    )

    def __init__(self, indexes: Sequence[int]) -> None:
        super().__init__(f"{len(indexes)} selected tasks are not the caller's to change.")
        self.details = _positions(indexes, "id", "Not yours to change.")


class BulkTaskConflictError(Exception):
    """Some of the selected tasks changed after the caller read them.

    Also raised when a concurrent save lands between the checks and the write;
    then the positions are unknown, and the detail list is empty.
    """

    code = "TASK_CONFLICT"
    message = (
        "Some of the selected tasks were changed by someone else after you opened them. "
        "Reload them to see the latest versions. Nothing was changed."
    )

    def __init__(self, indexes: Sequence[int] = ()) -> None:
        super().__init__(f"{len(indexes)} selected tasks changed concurrently.")
        self.details = _positions(indexes, "version", "Changed by someone else.")


class TaskLabelLimitError(Exception):
    """Adding these labels would put some tasks over the per-task limit."""

    code = "TASK_LABEL_LIMIT"
    message = f"A task can carry at most {MAX_LABELS_PER_TASK} labels. Nothing was changed."

    def __init__(self, indexes: Sequence[int]) -> None:
        super().__init__(f"{len(indexes)} selected tasks would carry too many labels.")
        self.details = _positions(indexes, "id", "Would carry too many labels.")
