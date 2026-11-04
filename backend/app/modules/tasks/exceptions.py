"""Domain/application exceptions for the tasks module."""

import uuid


class TaskNotFoundError(Exception):
    """The requested task does not exist (or is not visible)."""

    code = "TASK_NOT_FOUND"
    message = "The requested task was not found."

    def __init__(self, task_id: uuid.UUID) -> None:
        super().__init__(f"Task {task_id} was not found.")
        self.task_id = task_id
