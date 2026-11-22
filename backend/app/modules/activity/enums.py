"""Enumerations for the activity domain.

Values are stored as lowercase strings and are part of the public API contract.
Do not rename existing values; add new ones (architecture doc section 6).
"""

from enum import StrEnum


class ActivityVerb(StrEnum):
    """What happened. The fields that changed are in the event's ``changes``."""

    TASK_CREATED = "task.created"
    TASK_UPDATED = "task.updated"
    """One save: any mix of status, priority, title, description, due date,
    assignee and project, each recorded as ``{"from": ..., "to": ...}``."""
    TASK_DELETED = "task.deleted"
    DEPENDENCY_ADDED = "dependency.added"
    """The task now waits on another: ``{"blocked_by": {"from": None, "to": ref}}``,
    ``ref`` being the blocking task's ``{"id", "name"}`` as it was titled then."""
    DEPENDENCY_REMOVED = "dependency.removed"
    """The task no longer waits on one: ``{"blocked_by": {"from": ref, "to": None}}``."""
    AUTOMATION_NOTIFIED = "automation.notified"
    """A workspace automation rule told people the task was finished:
    ``{"notified": {"from": None, "to": [ref, ...]}, "rules": {"from": None, "to":
    [rule, ...]}}`` --- who was told, as ``{"id", "name"}`` snapshots, and which
    rules were on. The actor is whoever finished the task: it ran because of them.
    Recorded only when someone was actually told."""
    COMMENT_ADDED = "comment.added"
    COMMENT_EDITED = "comment.edited"
    COMMENT_DELETED = "comment.deleted"
