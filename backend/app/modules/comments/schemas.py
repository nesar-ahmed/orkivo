"""Pydantic request/response contracts for the comments module.

SQLAlchemy models are never exposed directly as API responses
(architecture doc section 4.2).
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.comments.models import MAX_BODY_LENGTH

CommentBody = Annotated[str, Field(min_length=1, max_length=MAX_BODY_LENGTH)]


class CommentCreate(BaseModel):
    """Say something on a task.

    Mention a member by writing ``<@their-user-id>`` in the body; they are told,
    and readers see their name. A token naming anyone who is not a member of the
    task's workspace is kept as text and does nothing.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    body: CommentBody


class CommentUpdate(BaseModel):
    """Change what you said. The text is replaced and ``edited_at`` is set."""

    model_config = ConfigDict(str_strip_whitespace=True)

    body: CommentBody


class CommentPerson(BaseModel):
    """Who wrote a comment: enough to recognise, never an email."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str


class CommentRead(BaseModel):
    """Public representation of a comment."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    body: str
    # ``None`` only if the account is gone.
    author: CommentPerson | None
    # The members the body's ``<@id>`` tokens name, so a client can show names.
    # Anyone no longer a member is left out, and reads as "@someone".
    mentions: list[CommentPerson] = Field(default_factory=list)
    # Set once the author changes the text.
    edited_at: datetime | None
    created_at: datetime


class CommentListResponse(BaseModel):
    """Paginated collection envelope, oldest first (architecture doc sections 6 and 7)."""

    items: list[CommentRead]
    total: int
    page: int
    page_size: int
    pages: int
