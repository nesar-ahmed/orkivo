"""Domain/application exceptions for the tasks module."""

import uuid


class TaskNotFoundError(Exception):
    """The requested task does not exist (or is not visible)."""

    code = "TASK_NOT_FOUND"
    message = "The requested task was not found."

    def __init__(self, task_id: uuid.UUID) -> None:
        super().__init__(f"Task {task_id} was not found.")
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
