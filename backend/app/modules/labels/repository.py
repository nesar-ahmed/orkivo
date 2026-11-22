"""Database access for the labels module.

The repository encapsulates queries only. It does not decide authorization
policy and does not return HTTP responses; transaction commits happen at the
service layer (architecture doc sections 4.1 and 6.2).

Who may read a tenant is decided by ``workspaces.access`` before any function
here runs. Every list and name lookup still carries the tenant predicate, so a
label can only ever be found in the one workspace that was authorized.
"""

import uuid
from collections.abc import Collection, Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.modules.labels.models import Label, name_key


def list_labels(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
) -> tuple[Sequence[Label], int]:
    """One page of a tenant's labels, alphabetically, plus the total count.

    Alphabetical, like projects: labels are picked from menus, where a stable
    order matters more than recency.
    """
    stmt: Select[Label] = (
        select(Label)
        .where(Label.workspace_id == workspace_id)
        .order_by(Label.name_key, Label.id)
    )
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = session.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return items, total


def count_in_workspace(session: Session, workspace_id: uuid.UUID) -> int:
    """How many labels a tenant holds, for the per-workspace limit."""
    return (
        session.scalar(
            select(func.count()).select_from(Label).where(Label.workspace_id == workspace_id)
        )
        or 0
    )


def get_label(session: Session, label_id: uuid.UUID) -> Label | None:
    """Fetch a label by id, *before* authorization.

    Deliberately unscoped, like ``projects.repository.get_project``: which
    workspace holds the label is what the service needs to ask the access policy.
    """
    return session.get(Label, label_id)


def list_in_workspace(
    session: Session, workspace_id: uuid.UUID, label_ids: Collection[uuid.UUID]
) -> Sequence[Label]:
    """Those of ``label_ids`` that live in ``workspace_id``, alphabetically."""
    if not label_ids:
        return []
    return session.scalars(
        select(Label)
        .where(Label.workspace_id == workspace_id, Label.id.in_(list(label_ids)))
        .order_by(Label.name_key, Label.id)
    ).all()


def name_taken(
    session: Session,
    workspace_id: uuid.UUID,
    name: str,
    *,
    excluding: uuid.UUID | None = None,
) -> bool:
    """Whether another label in the tenant already has this name, ignoring case.

    Served by the ``(workspace_id, name_key)`` unique constraint, which is also
    what settles a race.
    """
    stmt = select(Label.id).where(
        Label.workspace_id == workspace_id, Label.name_key == name_key(name)
    )
    if excluding is not None:
        stmt = stmt.where(Label.id != excluding)
    return session.scalars(stmt.limit(1)).first() is not None


def add_label(session: Session, label: Label) -> None:
    session.add(label)
    session.flush()


def delete_label(session: Session, label: Label) -> None:
    session.delete(label)
