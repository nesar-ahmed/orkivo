"""Application service implementing label use cases.

Business rules live here, not in route handlers. Transaction boundaries are
committed at this use-case layer and rolled back on failure
(architecture doc section 6.2).

Whether the acting user may touch a workspace's labels is decided by
``workspaces.access.WorkspaceAccessPolicy`` --- never here. This service only
names the action it is attempting, with the same split as projects:

==============================  ======================  ==============================
Use case                        Action                  Who, in an active tenant
==============================  ======================  ==============================
List and read labels            ``read``                every member
Create, rename, recolor         ``manage_labels``       owners, admins and managers
Delete                          ``manage``              owners and admins
==============================  ======================  ==============================

Members tag their tasks with labels --- that is editing the task --- but the
workspace's vocabulary of labels is kept by the people running the work.

Deleting is ``manage`` because it changes everyone's work at once: the label is
taken off every task that carries it, in this same transaction, by the tasks
module. A suspended company is in view mode, so only reads succeed there, and a
label in a workspace the caller is not in reads as not found, exactly like one
that does not exist (architecture doc sections 7 and 9).

A workspace holds at most ``MAX_LABELS_PER_WORKSPACE`` labels. The count is
checked before each insert; two members creating the last label at the same
instant can overshoot by one, which is harmless --- the limit exists so that a
picker can always show every label, not as an invariant.
"""

import math
import uuid
from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.modules.labels import repository
from app.modules.labels.exceptions import (
    LabelConflictError,
    LabelLimitReachedError,
    LabelNameInUseError,
    LabelNotFoundError,
)
from app.modules.labels.models import Label
from app.modules.labels.schemas import LabelCreate, LabelUpdate
from app.modules.tasks.label_links import count_by_label, detach_label
from app.modules.users.models import User
from app.modules.workspaces.access import WorkspaceAccessPolicy
from app.modules.workspaces.enums import WorkspaceAction

#: The API's page-size ceiling: one request can always list every label.
MAX_LABELS_PER_WORKSPACE = 100


class LabelService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._access = WorkspaceAccessPolicy(session)

    # --- collections (addressed by workspace) -------------------------------
    def create_label(self, workspace_id: uuid.UUID, data: LabelCreate, *, actor: User) -> Label:
        access = self._access.require(
            workspace_id, actor=actor, action=WorkspaceAction.MANAGE_LABELS
        )
        if repository.name_taken(self._session, access.workspace.id, data.name):
            raise LabelNameInUseError
        if repository.count_in_workspace(self._session, access.workspace.id) >= (
            MAX_LABELS_PER_WORKSPACE
        ):
            raise LabelLimitReachedError(MAX_LABELS_PER_WORKSPACE)
        label = Label(**data.model_dump(), workspace_id=access.workspace.id, created_by=actor)
        try:
            repository.add_label(self._session, label)
        except IntegrityError:
            # Someone created the same name between the check and the insert.
            self._session.rollback()
            raise LabelNameInUseError from None
        self._commit()
        return label

    def list_labels(
        self,
        workspace_id: uuid.UUID,
        *,
        actor: User,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[tuple[Label, int]], int, int]:
        """One page of a tenant's labels, each with how many tasks carry it."""
        access = self._access.require(workspace_id, actor=actor, action=WorkspaceAction.READ)
        labels, total = repository.list_labels(
            self._session, workspace_id=access.workspace.id, page=page, page_size=page_size
        )
        counts = count_by_label(self._session, [label.id for label in labels])
        rows = [(label, counts[label.id]) for label in labels]
        return rows, total, _pages(total, page, page_size)

    # --- single labels (addressed by id) ------------------------------------
    def get_label(self, label_id: uuid.UUID, *, actor: User) -> Label:
        return self._authorized_label(label_id, actor=actor, action=WorkspaceAction.READ)

    def update_label(self, label_id: uuid.UUID, data: LabelUpdate, *, actor: User) -> Label:
        label = self._authorized_label(label_id, actor=actor, action=WorkspaceAction.MANAGE_LABELS)
        self._check_version(label, data.version)
        changes = data.model_dump(exclude_unset=True, exclude={"version"})
        if not changes:
            return label
        name = changes.get("name")
        if name is not None and repository.name_taken(
            self._session, label.workspace_id, name, excluding=label.id
        ):
            raise LabelNameInUseError
        for field, value in changes.items():
            setattr(label, field, value)
        self._write(label_id)
        return label

    def delete_label(self, label_id: uuid.UUID, *, actor: User, version: int | None = None) -> None:
        """Delete a label and take it off every task, in one transaction.

        Optionally only if nobody changed the label since ``version``.
        """
        label = self._authorized_label(label_id, actor=actor, action=WorkspaceAction.MANAGE)
        self._check_version(label, version)
        detach_label(self._session, label=label, actor=actor)
        repository.delete_label(self._session, label)
        self._write(label_id)

    # --- helpers -----------------------------------------------------------
    def _authorized_label(
        self, label_id: uuid.UUID, *, actor: User, action: WorkspaceAction
    ) -> Label:
        """The label, once the policy allows ``action`` in the workspace holding it.

        Missing label and "in a workspace you are not in" both raise
        ``LabelNotFoundError`` with the same payload.
        """
        label = repository.get_label(self._session, label_id)
        if label is None:
            raise LabelNotFoundError(label_id)
        self._access.require_for_content(
            label.workspace_id,
            actor=actor,
            action=action,
            hidden_as=LabelNotFoundError(label_id),
        )
        return label

    @staticmethod
    def _check_version(label: Label, expected: int | None) -> None:
        if expected is not None and expected != label.version:
            raise LabelConflictError(label.id)

    def _write(self, label_id: uuid.UUID) -> None:
        """Flush and commit; a lost race becomes a 409 of the matching kind."""
        try:
            self._session.flush()
        except StaleDataError:
            self._session.rollback()
            raise LabelConflictError(label_id) from None
        except IntegrityError:
            # Only the case-insensitive name constraint can refuse a label write.
            self._session.rollback()
            raise LabelNameInUseError from None
        self._commit()

    def _commit(self) -> None:
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise


def _pages(total: int, page: int, page_size: int) -> int:
    """Page count for the collection envelope."""
    return math.ceil(total / page_size) if total else 0
