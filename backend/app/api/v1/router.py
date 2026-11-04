"""v1 router composition.

New modules are wired here as they are implemented. The initial release
contains only the ``tasks`` module (see README for scope notes).
"""

from fastapi import APIRouter

from app.api.v1 import health
from app.modules.tasks.router import router as tasks_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(tasks_router)
