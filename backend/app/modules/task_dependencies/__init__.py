"""Task dependencies module: which task is waiting on which.

Owns: the links between a task and the tasks blocking it, and the rules that keep
them meaningful --- both in one workspace, never a task on itself, never a cycle.
Does not own: the tasks themselves (``tasks``), or who may touch a tenant at all
--- a dependency is reached through its task, by the same rule as the task
(``TaskService.authorized_task``), like a comment (architecture doc section 5).

Dependencies *inform* rather than enforce: a blocked task can still be started or
finished. The tasks module asks this module's public ``blockers`` how many open
tasks still block each task it returns, and tells it when a task is done, so the
people waiting on it hear that they are unblocked.
"""
