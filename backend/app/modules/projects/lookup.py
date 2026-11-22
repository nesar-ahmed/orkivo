"""What the projects module offers a search across workspaces.

The public answer to "which projects are called something like this?", for the
``search`` module, which owns no projects (architecture doc section 5). It
authorizes nobody: the caller passes only tenants the access policy returned.
"""

import uuid
from collections.abc import Collection, Sequence

from sqlalchemy.orm import Session

from app.modules.projects import repository
from app.modules.projects.models import Project


def find_projects(
    session: Session, *, workspace_ids: Collection[uuid.UUID], term: str, limit: int
) -> Sequence[Project]:
    """Up to ``limit`` projects whose name contains ``term``, best matches first."""
    return repository.find_by_name(session, workspace_ids=workspace_ids, term=term, limit=limit)
