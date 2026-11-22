"""Enumerations for the tasks domain.

Values are stored as lowercase strings and are part of the public API
contract. Do not rename existing values; document how they evolve
(architecture doc section 6).
"""

from enum import StrEnum


class TaskStatus(StrEnum):
    """Kanban board statuses."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StatusScope(StrEnum):
    """The named status filter, next to filtering by one status.

    ``open`` is everything not yet done --- what a person's own list shows by
    default, since finished work is rarely what they came to see.
    """

    OPEN = "open"


class AssigneeScope(StrEnum):
    """The named assignee filters, next to filtering by a member's id.

    ``me`` is resolved to the caller on the server, so a shared link such as
    ``?assignee=me`` shows each person their own work.
    """

    ME = "me"
    NONE = "none"


class ProjectScope(StrEnum):
    """The named project filter, next to filtering by a project's id."""

    NONE = "none"


class LabelScope(StrEnum):
    """The named label filter, next to filtering by a label's id."""

    NONE = "none"


class TaskOrder(StrEnum):
    """How a list of tasks is sorted.

    ``newest`` is the default. ``project`` keeps each project's tasks together
    (alphabetically by project, tasks without one last, newest first inside each),
    so a paginated list can be shown grouped by project. ``due`` puts the soonest
    due date first and tasks without one last, so a list reads as a schedule and
    can be grouped into "overdue", "today", "this week"; ties go to the higher
    priority. ``priority`` puts high before medium before low, soonest due first
    inside each.
    """

    NEWEST = "newest"
    PROJECT = "project"
    DUE = "due"
    PRIORITY = "priority"


class TaskAction(StrEnum):
    """What a caller may do to one task, beyond reading it.

    Part of the public API contract: every task the API returns lists the actions
    its caller may perform on it right now (``TaskRead.capabilities``), so the
    frontend renders the decision made in ``permissions`` instead of re-deriving
    it. Reading needs no entry: a task the caller cannot read is never returned.
    """

    EDIT = "edit"
    """Change any field, link or unlink its blockers."""

    DELETE = "delete"
