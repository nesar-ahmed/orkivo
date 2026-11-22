"""What the projects module offers content that *points at* a project.

A task names the project it is filed under. Whether that project exists, and
whether it lives in the task's own workspace, is this module's fact to state ---
so the tasks service asks here instead of reading the projects table itself
(architecture doc section 5).

It authorizes nobody: the caller must already hold access to ``workspace_id``
through ``workspaces.access``. A project missing from the answer is either in
another workspace or does not exist; callers must not tell the two apart.
"""

import uuid

from sqlalchemy.orm import Session

from app.modules.projects import repository
from app.modules.projects.models import Project


def project_in_workspace(
    session: Session, workspace_id: uuid.UUID, project_id: uuid.UUID
) -> Project | None:
    """The project, only if it is one of ``workspace_id``'s projects."""
    return repository.get_in_workspace(session, workspace_id, project_id)
