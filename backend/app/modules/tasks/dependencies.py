"""Module-specific dependencies for the tasks module."""

from typing import Annotated

from fastapi import Depends

from app.api.v1.deps import DbSession
from app.modules.tasks.service import TaskService


def get_task_service(db: DbSession) -> TaskService:
    return TaskService(db)


TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
