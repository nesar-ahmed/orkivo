"""Module-specific dependencies for the automations module."""

from typing import Annotated

from fastapi import Depends

from app.api.v1.deps import DbSession
from app.modules.automations.service import AutomationService


def get_automation_service(db: DbSession) -> AutomationService:
    return AutomationService(db)


AutomationServiceDep = Annotated[AutomationService, Depends(get_automation_service)]
