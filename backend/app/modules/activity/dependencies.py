"""Module-specific dependencies for the activity module."""

from typing import Annotated

from fastapi import Depends

from app.api.v1.deps import DbSession
from app.modules.activity.service import ActivityService


def get_activity_service(db: DbSession) -> ActivityService:
    return ActivityService(db)


ActivityServiceDep = Annotated[ActivityService, Depends(get_activity_service)]
