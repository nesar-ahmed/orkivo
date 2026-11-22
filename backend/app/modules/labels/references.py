"""What the labels module offers content that *points at* labels.

A task names the labels it carries. Whether those labels exist, and whether they
live in the task's own workspace, is this module's fact to state --- so the tasks
service asks here instead of reading the labels table itself (architecture doc
section 5), exactly as it asks ``projects.references`` about a project.

It authorizes nobody: the caller must already hold access to ``workspace_id``
through ``workspaces.access``. A label missing from the answer is either in
another workspace or does not exist; callers must not tell the two apart.
"""

import uuid
from collections.abc import Collection, Mapping

from sqlalchemy.orm import Session

from app.modules.labels import repository
from app.modules.labels.models import Label


def labels_in_workspace(
    session: Session, workspace_id: uuid.UUID, label_ids: Collection[uuid.UUID]
) -> Mapping[uuid.UUID, Label]:
    """Those of ``label_ids`` that are ``workspace_id``'s labels, by id."""
    found = repository.list_in_workspace(session, workspace_id, label_ids)
    return {label.id: label for label in found}
