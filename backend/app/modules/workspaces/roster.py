"""What the workspaces module offers modules that report on a tenant's people.

The ``insights`` module shows how work is spread across a company's members; it
does not own membership (architecture doc section 5). This is the workspaces
module's public answer to "who is in this tenant, and in what role?", so nothing
else reads ``workspace_members`` to find out.

It authorizes nobody: the caller must already hold read access to ``workspace_id``
through ``access.WorkspaceAccessPolicy``. Every member may see the people list, so
the answer reveals nothing a member could not already read.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.modules.users.models import User
from app.modules.workspaces import repository
from app.modules.workspaces.enums import WorkspaceRole


def roster(session: Session, workspace_id: uuid.UUID) -> Sequence[tuple[User, WorkspaceRole]]:
    """Everyone in the tenant with their role, alphabetically by name."""
    return repository.list_roster(session, workspace_id)
