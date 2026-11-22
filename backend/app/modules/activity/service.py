"""Application service for reading the activity log.

Reading only: events are written by the services that make the changes, through
``recorder.ActivityRecorder`` (architecture doc section 6.2).

A task's history is reached exactly like the task --- ``TaskService.authorized_task``
--- so outsiders get ``TASK_NOT_FOUND`` and a suspended company stays readable.
A workspace's feed needs only ``read`` in it, and is the one place a deleted
task's history remains visible.
"""

import math
import uuid
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.modules.activity import repository
from app.modules.activity.models import ActivityEvent
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from app.modules.workspaces.access import WorkspaceAccessPolicy
from app.modules.workspaces.enums import WorkspaceAction


class ActivityService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._access = WorkspaceAccessPolicy(session)
        self._tasks = TaskService(session)

    def task_history(
        self, task_id: uuid.UUID, *, actor: User, page: int = 1, page_size: int = 20
    ) -> tuple[Sequence[ActivityEvent], int, int]:
        """One task's events, newest first."""
        task = self._tasks.authorized_task(task_id, actor=actor, action=WorkspaceAction.READ)
        items, total = repository.list_events(
            self._session,
            workspace_id=task.workspace_id,
            task_id=task.id,
            page=page,
            page_size=page_size,
        )
        return items, total, _pages(total, page, page_size)

    def workspace_feed(
        self, workspace_id: uuid.UUID, *, actor: User, page: int = 1, page_size: int = 20
    ) -> tuple[Sequence[ActivityEvent], int, int]:
        """Everything that happened in a workspace, newest first --- deleted tasks too."""
        access = self._access.require(workspace_id, actor=actor, action=WorkspaceAction.READ)
        items, total = repository.list_events(
            self._session, workspace_id=access.workspace.id, page=page, page_size=page_size
        )
        return items, total, _pages(total, page, page_size)


def _pages(total: int, page: int, page_size: int) -> int:
    """Page count for the collection envelope."""
    return math.ceil(total / page_size) if total else 0
