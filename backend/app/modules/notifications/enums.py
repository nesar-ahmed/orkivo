"""Enumerations for the notifications domain.

Values are stored as lowercase strings and are part of the public API contract.
Do not rename existing values; add new ones (architecture doc section 6).
"""

from enum import StrEnum


class NotificationKind(StrEnum):
    """Why someone is being told."""

    ASSIGNED = "assigned"
    """A task was assigned to them by someone else."""

    COMMENTED = "commented"
    """Someone commented on a task they watch."""

    MENTIONED = "mentioned"
    """Someone mentioned them in a comment. Replaces ``commented`` for that comment."""

    UNBLOCKED = "unblocked"
    """The last unfinished task blocking a task assigned to them was just done."""

    COMPLETED = "completed"
    """A task was moved to Done, and a workspace automation rule says they should
    hear about it (``automations``): they created it, watch it, or own the
    workspace."""
