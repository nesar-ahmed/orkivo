"""Pydantic response contracts for the activity module.

Read-only: there is no request body anywhere in this module, because nothing
about an event can be changed (architecture doc section 4.2).
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.activity.enums import ActivityVerb


class ActivityPerson(BaseModel):
    """Who did it: enough to recognise, never an email."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str


class FieldChange(BaseModel):
    """One field's value before and after, as it was at the time.

    People and projects are ``{"id", "name"}`` snapshots; a description change is
    recorded in full; everything else is the plain value or ``null``.
    """

    model_config = ConfigDict(populate_by_name=True)

    from_: Any = Field(default=None, alias="from")
    to: Any = None


class ActivityRead(BaseModel):
    """One event in a task's history or a workspace's feed."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    verb: ActivityVerb
    # Kept after the task is deleted, so the feed can still name it.
    task_id: UUID | None
    task_title: str | None
    task_version: int | None
    comment_id: UUID | None
    # ``None`` only if the account is gone.
    actor: ActivityPerson | None
    changes: dict[str, FieldChange]
    created_at: datetime


class ActivityListResponse(BaseModel):
    """Paginated collection envelope, newest first (architecture doc sections 6 and 7)."""

    items: list[ActivityRead]
    total: int
    page: int
    page_size: int
    pages: int
