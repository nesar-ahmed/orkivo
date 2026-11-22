"""Enumerations for the automations domain.

Values are stored as lowercase strings and are part of the public API contract.
Do not rename existing values; add new ones (architecture doc section 6).
"""

from enum import StrEnum


class AutomationTrigger(StrEnum):
    """What makes a rule run."""

    TASK_COMPLETED = "task_completed"
    """A task was moved to Done --- by a save, a bulk save or a board drag alike.
    Creating a task that is already done is not moving it there."""


class AutomationRecipient(StrEnum):
    """Who a notifying rule tells."""

    TASK_CREATOR = "task_creator"
    """Whoever created the task: its owner in the tasks module's words."""

    TASK_WATCHERS = "task_watchers"
    """Everyone following the task."""

    WORKSPACE_OWNERS = "workspace_owners"
    """The workspace's owners, whoever created or holds the task."""


class AutomationRule(StrEnum):
    """A rule a workspace can switch on: a trigger and what it does.

    The catalogue, in the order a settings page offers it. What each rule means is
    ``catalog.RULES``; this names them.
    """

    NOTIFY_CREATOR_ON_DONE = "notify_creator_on_done"
    NOTIFY_WATCHERS_ON_DONE = "notify_watchers_on_done"
    NOTIFY_OWNERS_ON_DONE = "notify_owners_on_done"
