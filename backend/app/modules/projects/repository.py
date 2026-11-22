"""Database access for the projects module.

The repository encapsulates queries only. It does not decide authorization
policy and does not return HTTP responses; transaction commits happen at the
service layer (architecture doc sections 4.1 and 6.2).

Who may read a tenant is decided by ``workspaces.access`` before any function
here runs. Every list and name lookup still carries the tenant predicate, so a
project can only ever be found in the one workspace that was authorized.
"""

import uuid
from collections.abc import Collection, Sequence

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session

from app.modules.projects.models import Project, name_key


def list_projects(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
) -> tuple[Sequence[Project], int]:
    """One page of a tenant's projects, alphabetically, plus the total count.

    Alphabetical rather than newest first: projects are picked from menus and
    scanned as lanes on a board, where a stable order matters more than recency.
    """
    stmt: Select[Project] = (
        select(Project)
        .where(Project.workspace_id == workspace_id)
        .order_by(Project.name_key, Project.id)
    )
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = session.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return items, total


def get_project(session: Session, project_id: uuid.UUID) -> Project | None:
    """Fetch a project by id, *before* authorization.

    Deliberately unscoped, like ``tasks.repository.get_task``: which workspace
    holds the project is what the service needs to ask the access policy.
    """
    return session.get(Project, project_id)


def get_in_workspace(
    session: Session, workspace_id: uuid.UUID, project_id: uuid.UUID
) -> Project | None:
    """The project, only if it lives in ``workspace_id``."""
    return session.scalars(
        select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
    ).first()


def name_taken(
    session: Session,
    workspace_id: uuid.UUID,
    name: str,
    *,
    excluding: uuid.UUID | None = None,
) -> bool:
    """Whether another project in the tenant already has this name, ignoring case.

    Served by the ``(workspace_id, name_key)`` unique constraint, which is also
    what settles a race.
    """
    stmt = select(Project.id).where(
        Project.workspace_id == workspace_id, Project.name_key == name_key(name)
    )
    if excluding is not None:
        stmt = stmt.where(Project.id != excluding)
    return session.scalars(stmt.limit(1)).first() is not None


def find_by_name(
    session: Session, *, workspace_ids: Collection[uuid.UUID], term: str, limit: int
) -> Sequence[Project]:
    """Projects whose name contains ``term``, in these tenants only.

    A name that starts with the term comes first, then alphabetically.
    ``icontains`` escapes LIKE wildcards in what was typed.
    """
    if not workspace_ids:
        return []
    rank = case((Project.name.istartswith(term, autoescape=True), 0), else_=1)
    return session.scalars(
        select(Project)
        .where(
            Project.workspace_id.in_(list(workspace_ids)),
            Project.name.icontains(term, autoescape=True),
        )
        .order_by(rank, Project.name_key, Project.id)
        .limit(limit)
    ).all()


def add_project(session: Session, project: Project) -> None:
    session.add(project)
    session.flush()


def delete_project(session: Session, project: Project) -> None:
    session.delete(project)
