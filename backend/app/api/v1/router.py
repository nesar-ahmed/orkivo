"""v1 router composition.

New modules are wired here as they are implemented. The current release
contains ``auth``, ``users``, ``workspaces`` and ``tasks`` (see README for scope
notes).
"""

from fastapi import APIRouter

from app.api.v1 import health
from app.modules.auth.router import router as auth_router
from app.modules.tasks.router import router as tasks_router
from app.modules.users.router import router as users_router
from app.modules.workspaces.router import platform_router as workspace_platform_router
from app.modules.workspaces.router import router as workspaces_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(workspaces_router)
api_router.include_router(workspace_platform_router)
api_router.include_router(tasks_router)
