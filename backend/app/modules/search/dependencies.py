"""Module-specific dependencies for the search module."""

from typing import Annotated

from fastapi import Depends

from app.api.v1.deps import DbSession
from app.modules.search.service import SearchService


def get_search_service(db: DbSession) -> SearchService:
    return SearchService(db)


SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]
