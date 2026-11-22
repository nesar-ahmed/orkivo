"""How changes to tasks are described in the activity log.

One place decides what an event says about a task --- which fields are tracked,
and how a person, project or label is written down --- so a save, a member
leaving, a project being deleted and a label being deleted all produce events of
the same shape.

People, projects and labels are recorded as ``{"id", "name"}`` snapshots taken
at the time, so "assigned to Mo" still reads that way after Mo renames themselves
or the project is deleted. A task's labels are a list of those snapshots,
alphabetical, and ``[]`` when it carries none. Everything is plain JSON.
"""

from typing import Any

from app.modules.labels.models import Label
from app.modules.projects.models import Project
from app.modules.tasks.models import Task
from app.modules.users.models import User

#: The fields a ``task.updated`` event can report, in the order a reader expects.
TRACKED_FIELDS = (
    "title",
    "status",
    "priority",
    "assignee",
    "project",
    "labels",
    "due_date",
    "description",
)


def person(user: User | None) -> dict[str, str] | None:
    return {"id": str(user.id), "name": user.display_name} if user is not None else None


def project_ref(project: Project | None) -> dict[str, str] | None:
    return {"id": str(project.id), "name": project.name} if project is not None else None


def label_ref(label: Label) -> dict[str, str]:
    return {"id": str(label.id), "name": label.name}


def label_refs(labels: list[Label]) -> list[dict[str, str]]:
    """A set of labels as it is written down: alphabetical, like the API lists them."""
    ordered = sorted(labels, key=lambda label: (label.name_key, str(label.id)))
    return [label_ref(label) for label in ordered]


#: What a task holds before anything is set: nothing, and no labels.
_EMPTY: dict[str, Any] = {**{field: None for field in TRACKED_FIELDS}, "labels": []}


def snapshot(task: Task) -> dict[str, Any]:
    """The tracked fields of ``task`` as JSON values."""
    return {
        "title": task.title,
        "status": str(task.status),
        "priority": str(task.priority),
        "assignee": person(task.assignee),
        "project": project_ref(task.project),
        "labels": label_refs(task.labels),
        "due_date": task.due_date.isoformat() if task.due_date is not None else None,
        "description": task.description,
    }


def diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """``{field: {"from", "to"}}`` for every tracked field that changed.

    People and projects compare by id, so a rename between the two snapshots is
    not mistaken for a reassignment; a list of labels compares as a set of ids.
    """
    changes: dict[str, dict[str, Any]] = {}
    for field in TRACKED_FIELDS:
        old, new = before.get(field), after.get(field)
        if _identity(old) != _identity(new):
            changes[field] = {"from": old, "to": new}
    return changes


def initial(task: Task) -> dict[str, dict[str, Any]]:
    """What a new task started with, for its ``task.created`` event.

    Only what differs from an empty task, so the event says "created in Website,
    assigned to Mo" rather than listing every default.
    """
    return diff(_EMPTY, {k: v for k, v in snapshot(task).items() if k != "title"})


def _identity(value: Any) -> Any:
    if isinstance(value, list):
        return frozenset(_identity(item) for item in value)
    return value.get("id") if isinstance(value, dict) else value
