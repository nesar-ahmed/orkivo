"""Pydantic request/response contracts for the labels module.

SQLAlchemy models are never exposed directly as API responses
(architecture doc section 4.2).
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.labels.enums import LabelColor
from app.modules.labels.models import NAME_MAX_LENGTH

LabelName = Annotated[str, Field(min_length=1, max_length=NAME_MAX_LENGTH)]


class LabelCreate(BaseModel):
    """Input contract for creating a label in a workspace."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: LabelName
    color: LabelColor = LabelColor.GRAY


class LabelUpdate(BaseModel):
    """Partial update contract; only supplied fields are changed.

    ``name`` and ``color`` always have a value, so an explicit ``null`` is a
    validation error. ``version`` is the version the client last read: when
    supplied and stale, the update is refused with ``409 LABEL_CONFLICT``.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    name: LabelName | None = None
    color: LabelColor | None = None
    version: Annotated[int | None, Field(default=None, ge=1)] = None

    @field_validator("name", "color")
    @classmethod
    def _fields_cannot_be_cleared(cls, value: object) -> object:
        # Runs only when the field was supplied, so omitting it stays fine.
        if value is None:
            raise ValueError("This field cannot be empty.")
        return value


class LabelPerson(BaseModel):
    """Who created a label: enough to recognise, never an email."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str


class LabelRead(BaseModel):
    """Public representation of a label."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    color: LabelColor
    # Increments on every change; send it back on update or delete.
    version: int
    # ``None`` only if the account is gone.
    created_by: LabelPerson | None
    created_at: datetime
    updated_at: datetime


class LabelSummaryRead(LabelRead):
    """A label in its workspace's list, with how many tasks carry it.

    Counted by the tasks module on the same request, so the number is never a
    cached guess. It is also what deleting the label would take it off.
    """

    task_count: int


class LabelListResponse(BaseModel):
    """Paginated collection envelope (architecture doc sections 6 and 7)."""

    items: list[LabelSummaryRead]
    total: int
    page: int
    page_size: int
    pages: int
