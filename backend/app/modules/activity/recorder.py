"""How other modules write to the activity log.

A service that changes something builds an ``ActivityRecorder`` on *its own*
session and records the event before it commits. The recorder never flushes or
commits, so the event and the change it describes are one transaction: a save
refused with ``409`` or ``403``, or a race lost at flush, rolls the event back
with it, and a committed change can never be missing its event
(architecture doc section 6.2).
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.modules.activity import repository
from app.modules.activity.enums import ActivityVerb
from app.modules.activity.models import ActivityEvent
from app.modules.users.models import User


class ActivityRecorder:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        verb: ActivityVerb,
        *,
        workspace_id: uuid.UUID,
        actor: User | None,
        task_id: uuid.UUID | None,
        task_title: str | None,
        task_version: int | None = None,
        comment_id: uuid.UUID | None = None,
        changes: dict[str, Any] | None = None,
    ) -> ActivityEvent:
        """Add one event to the caller's transaction and return it.

        ``changes`` maps a field to ``{"from": ..., "to": ...}`` using JSON values
        only --- strings, numbers, ``None``, or ``{"id", "name"}`` snapshots for
        people and projects --- so the event reads the same forever.
        """
        event = ActivityEvent(
            verb=verb,
            workspace_id=workspace_id,
            actor=actor,
            task_id=task_id,
            task_title=task_title,
            task_version=task_version,
            comment_id=comment_id,
            changes=changes or {},
        )
        repository.append(self._session, event)
        return event
