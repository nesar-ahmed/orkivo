"""Pydantic response contracts for the notifications module.

SQLAlchemy models are never exposed directly as API responses
(architecture doc section 4.2). Nothing in an inbox row carries an email.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.notifications.enums import NotificationKind
from app.modules.workspaces.enums import WorkspaceKind


class NotificationPerson(BaseModel):
    """Who did it, or who is watching: enough to recognise, never an email."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str


class NotificationTask(BaseModel):
    """The task a notification is about, by its current title."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str


class NotificationWorkspace(BaseModel):
    """Where the task lives: enough for the client to build the task's address."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    kind: WorkspaceKind
    slug: str | None


class NotificationRead(BaseModel):
    """One inbox row."""

    id: UUID
    kind: NotificationKind
    # ``None`` only if the account is gone.
    actor: NotificationPerson | None
    task: NotificationTask
    workspace: NotificationWorkspace
    comment_id: UUID | None
    # The start of the comment, mentions shown as ``@Name``; ``None`` otherwise.
    excerpt: str | None
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Paginated envelope, newest first, with the unread count for the badge."""

    items: list[NotificationRead]
    total: int
    unread: int
    page: int
    page_size: int
    pages: int


class UnreadCountRead(BaseModel):
    """Just the number, for the badge: cheap enough to poll."""

    count: int


class WatchersRead(BaseModel):
    """Who follows a task, and whether the caller is one of them."""

    items: list[NotificationPerson]
    watching: bool
