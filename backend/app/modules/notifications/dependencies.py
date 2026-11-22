"""Module-specific dependencies for the notifications module."""

from typing import Annotated

from fastapi import Depends

from app.api.v1.deps import DbSession
from app.modules.notifications.service import NotificationService


def get_notification_service(db: DbSession) -> NotificationService:
    return NotificationService(db)


NotificationServiceDep = Annotated[NotificationService, Depends(get_notification_service)]
