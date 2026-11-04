"""Application service implementing task use cases.

Business rules live here, not in route handlers. Transaction boundaries are
committed at this use-case layer and rolled back on failure
(architecture doc section 6.2).
"""

import uuid
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.modules.tasks import repository
from app.modules.tasks.enums import TaskPriority, TaskStatus
from app.modules.tasks.exceptions import TaskNotFoundError
from app.modules.tasks.models import Task
from app.modules.tasks.schemas import TaskCreate, TaskUpdate


class TaskService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_task(self, data: TaskCreate) -> Task:
        task = Task(**data.model_dump())
        repository.add_task(self._session, task)
        self._commit()
        return task

    def get_task(self, task_id: uuid.UUID) -> Task:
        task = repository.get_task(self._session, task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    def list_tasks(
        self,
        *,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[Task], int]:
        return repository.list_tasks(
            self._session,
            status=status,
            priority=priority,
            search=search,
            page=page,
            page_size=page_size,
        )

    def update_task(self, task_id: uuid.UUID, data: TaskUpdate) -> Task:
        task = self.get_task(task_id)
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(task, field, value)
        self._session.flush()
        self._commit()
        return task

    def delete_task(self, task_id: uuid.UUID) -> None:
        task = self.get_task(task_id)
        repository.delete_task(self._session, task)
        self._commit()

    def _commit(self) -> None:
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
