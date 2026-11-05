"""Module-specific dependencies for the workspaces module."""

from typing import Annotated

from fastapi import Depends

from app.api.v1.deps import DbSession
from app.modules.workspaces.service import WorkspaceService


def get_workspace_service(db: DbSession) -> WorkspaceService:
    return WorkspaceService(db)


WorkspaceServiceDep = Annotated[WorkspaceService, Depends(get_workspace_service)]
