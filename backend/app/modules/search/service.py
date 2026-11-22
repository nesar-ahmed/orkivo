"""Application service for search across the caller's workspaces.

Reading only. The scope is exactly the tenants the access policy says the caller
may read now (``readable``) --- the same set their own task list spans --- so search
can never return, or confirm the existence of, anything in a workspace they are not
in. A suspended company stays searchable, as it stays readable (view mode).

Matching is case-insensitive "contains", with what was typed escaped: a ``%`` or
``_`` is a character, not a wildcard. Within each kind, names that start with the
term rank first. Workspaces are matched here, in memory --- a person is in a
handful --- and tasks and projects by one query each in their own modules.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.modules.projects.lookup import find_projects
from app.modules.projects.models import Project
from app.modules.tasks.lookup import find_tasks
from app.modules.tasks.models import Task
from app.modules.users.models import User
from app.modules.workspaces.access import WorkspaceAccessPolicy
from app.modules.workspaces.enums import WorkspaceKind
from app.modules.workspaces.models import Workspace

#: What a private workspace is called wherever people see it, so it can be found
#: by that name rather than by the one stored at registration.
PRIVATE_WORKSPACE_NAME = "Private workspace"


@dataclass(frozen=True)
class SearchResults:
    """What matched, per kind, best first; tasks and projects with their workspace."""

    workspaces: Sequence[Workspace]
    projects: Sequence[tuple[Project, Workspace]]
    tasks: Sequence[tuple[Task, Workspace]]


class SearchService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._access = WorkspaceAccessPolicy(session)

    def search(self, term: str, *, actor: User, limit: int) -> SearchResults:
        """Up to ``limit`` of each kind whose name contains ``term``."""
        term = term.strip()
        if not term:
            return SearchResults(workspaces=[], projects=[], tasks=[])
        workspaces = {
            access.workspace.id: access.workspace for access in self._access.readable(actor=actor)
        }
        projects = find_projects(
            self._session, workspace_ids=workspaces.keys(), term=term, limit=limit
        )
        tasks = find_tasks(self._session, workspace_ids=workspaces.keys(), term=term, limit=limit)
        return SearchResults(
            workspaces=_matching(workspaces.values(), term)[:limit],
            projects=[(project, workspaces[project.workspace_id]) for project in projects],
            tasks=[(task, workspaces[task.workspace_id]) for task in tasks],
        )


def _matching(workspaces: Iterable[Workspace], term: str) -> list[Workspace]:
    """Workspaces whose name or address contains ``term``; names starting with it first."""
    wanted = term.casefold()
    found: list[tuple[int, str, Workspace]] = []
    for workspace in workspaces:
        name = (
            PRIVATE_WORKSPACE_NAME if workspace.kind is WorkspaceKind.PERSONAL else workspace.name
        )
        haystacks = [name.casefold(), (workspace.slug or "").casefold()]
        if not any(wanted in haystack for haystack in haystacks):
            continue
        starts = any(haystack.startswith(wanted) for haystack in haystacks)
        found.append((0 if starts else 1, name.casefold(), workspace))
    return [workspace for _rank, _name, workspace in sorted(found, key=lambda item: item[:2])]
