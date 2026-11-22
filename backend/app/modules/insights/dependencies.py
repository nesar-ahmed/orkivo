"""Module-specific dependencies for the insights module."""

from typing import Annotated

from fastapi import Depends

from app.api.v1.deps import DbSession
from app.modules.insights.service import InsightService


def get_insight_service(db: DbSession) -> InsightService:
    return InsightService(db)


InsightServiceDep = Annotated[InsightService, Depends(get_insight_service)]
