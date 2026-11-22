"""Module-specific dependencies for the labels module."""

from typing import Annotated

from fastapi import Depends

from app.api.v1.deps import DbSession
from app.modules.labels.service import LabelService


def get_label_service(db: DbSession) -> LabelService:
    return LabelService(db)


LabelServiceDep = Annotated[LabelService, Depends(get_label_service)]
