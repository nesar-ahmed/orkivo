"""What the tasks module offers a search across workspaces.

The ``search`` module answers "find X anywhere I can look"; it does not own the
tasks it finds (architecture doc section 5). This is the tasks module's public
answer to "which tasks are called something like this?", so nothing else reads the
tasks table to find out.

It authorizes nobody: the caller passes only tenants the access policy returned
(``WorkspaceAccessPolicy.readable``), and the query never looks outside them.
"""

import uuid
from collections.abc import Collection, Sequence

from sqlalchemy.orm import Session

from app.modules.tasks import repository
from app.modules.tasks.models import Task


def find_tasks(
    session: Session, *, workspace_ids: Collection[uuid.UUID], term: str, limit: int
) -> Sequence[Task]:
    """Up to ``limit`` tasks whose title contains ``term``, best matches first."""
    return repository.find_by_title(session, workspace_ids=workspace_ids, term=term, limit=limit)
