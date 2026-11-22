"""Module-specific dependencies for the projects module."""

from typing import Annotated

from fastapi import Depends

from app.api.v1.deps import DbSession
from app.modules.projects.service import ProjectService


def get_project_service(db: DbSession) -> ProjectService:
    return ProjectService(db)


ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
