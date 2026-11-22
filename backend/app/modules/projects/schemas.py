"""Pydantic request/response contracts for the projects module.

SQLAlchemy models are never exposed directly as API responses
(architecture doc section 4.2).
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProjectName = Annotated[str, Field(min_length=1, max_length=120)]
ProjectDescription = Annotated[str | None, Field(default=None, max_length=2000)]


class ProjectCreate(BaseModel):
    """Input contract for creating a project in a workspace."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: ProjectName
    description: ProjectDescription = None


class ProjectUpdate(BaseModel):
    """Partial update contract; only supplied fields are changed.

    ``description`` may be cleared with ``null``; ``name`` always has a value.
    ``version`` is the version the client last read: when supplied and stale,
    the update is refused with ``409 PROJECT_CONFLICT``.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    name: ProjectName | None = None
    description: ProjectDescription = None
    version: Annotated[int | None, Field(default=None, ge=1)] = None

    @field_validator("name")
    @classmethod
    def _name_cannot_be_cleared(cls, value: object) -> object:
        # Runs only when the field was supplied, so omitting it stays fine.
        if value is None:
            raise ValueError("This field cannot be empty.")
        return value


class ProjectPerson(BaseModel):
    """Who created a project: enough to recognise, never an email."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str


class ProjectRead(BaseModel):
    """Public representation of a project."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    description: str | None
    # Increments on every change; send it back on update or delete.
    version: int
    # ``None`` only if the account is gone.
    created_by: ProjectPerson | None
    created_at: datetime
    updated_at: datetime


class ProjectSummaryRead(ProjectRead):
    """A project in its workspace's list, with how much work it holds.

    Counted by the tasks module on the same request, so the numbers are never a
    cached guess: ``open_task_count`` is everything not yet done.
    """

    task_count: int
    open_task_count: int


class ProjectListResponse(BaseModel):
    """Paginated collection envelope (architecture doc sections 6 and 7)."""

    items: list[ProjectSummaryRead]
    total: int
    page: int
    page_size: int
    pages: int
