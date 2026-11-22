"""v1 router composition.

New modules are wired here as they are implemented. The current release
contains ``auth``, ``users``, ``workspaces``, ``projects``, ``labels``,
``tasks``, ``task_dependencies``, ``comments``, ``activity``, ``notifications``,
``insights``, ``automations`` and ``search`` (see README for scope notes).
"""

from fastapi import APIRouter

from app.api.v1 import health
from app.modules.activity.router import router as activity_router
from app.modules.auth.router import router as auth_router
from app.modules.automations.router import router as automations_router
from app.modules.comments.router import router as comments_router
from app.modules.insights.router import router as insights_router
from app.modules.labels.router import router as labels_router
from app.modules.notifications.router import router as notifications_router
from app.modules.projects.router import router as projects_router
from app.modules.search.router import router as search_router
from app.modules.task_dependencies.router import router as task_dependencies_router
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
api_router.include_router(projects_router)
api_router.include_router(labels_router)
api_router.include_router(tasks_router)
api_router.include_router(task_dependencies_router)
api_router.include_router(comments_router)
api_router.include_router(activity_router)
api_router.include_router(notifications_router)
api_router.include_router(insights_router)
api_router.include_router(automations_router)
api_router.include_router(search_router)
