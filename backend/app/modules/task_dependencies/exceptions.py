"""Domain/application exceptions for the task dependencies module."""

import uuid


class DependencyNotFoundError(Exception):
    """The task is not waiting on that task (or the link is not visible)."""

    code = "DEPENDENCY_NOT_FOUND"
    message = "This task is not blocked by that task."


class DependencyNotInWorkspaceError(Exception):
    """The chosen blocking task is not a task of the same workspace.

    One answer for "in another workspace" and "no such task", so a task id from
    elsewhere is never confirmed to exist.
    """

    code = "DEPENDENCY_NOT_IN_WORKSPACE"
    message = "A task can only be blocked by a task in its own workspace."

    def __init__(self, task_id: uuid.UUID) -> None:
        super().__init__(f"Task {task_id} cannot block tasks in this workspace.")
        self.task_id = task_id


class SelfDependencyError(Exception):
    """A task was asked to wait on itself."""

    code = "DEPENDENCY_ON_ITSELF"
    message = "A task cannot be blocked by itself."


class DependencyExistsError(Exception):
    """The task already waits on that task."""

    code = "DEPENDENCY_EXISTS"
    message = "This task is already blocked by that task."


class DependencyCycleError(Exception):
    """The new link would close a loop: the blocker already waits on this task.

    Work in a loop can never start, so the link is refused rather than recorded.
    """

    code = "DEPENDENCY_CYCLE"
    message = (
        "That task already waits on this one, directly or through other tasks, "
        "so it cannot also block it."
    )


class DependencyLimitReachedError(Exception):
    """The task already waits on as many tasks as it may."""

    code = "DEPENDENCY_LIMIT_REACHED"

    def __init__(self, limit: int) -> None:
        super().__init__(f"A task waits on at most {limit} tasks.")
        self.message = (
            f"This task is already blocked by {limit} tasks, the most it can be. "
            "Remove one first."
        )
