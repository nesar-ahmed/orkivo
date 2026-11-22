"""Module-specific dependencies for the task dependencies module."""

from typing import Annotated

from fastapi import Depends

from app.api.v1.deps import DbSession
from app.modules.task_dependencies.service import TaskDependencyService


def get_task_dependency_service(db: DbSession) -> TaskDependencyService:
    return TaskDependencyService(db)


TaskDependencyServiceDep = Annotated[TaskDependencyService, Depends(get_task_dependency_service)]
