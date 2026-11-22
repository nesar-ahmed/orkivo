"""Module-specific dependencies for the comments module."""

from typing import Annotated

from fastapi import Depends

from app.api.v1.deps import DbSession
from app.modules.comments.service import CommentService


def get_comment_service(db: DbSession) -> CommentService:
    return CommentService(db)


CommentServiceDep = Annotated[CommentService, Depends(get_comment_service)]
