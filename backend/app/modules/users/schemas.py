"""Pydantic request/response contracts for the users module.

SQLAlchemy models are never exposed directly as API responses, and the
password hash is not part of any contract (architecture doc section 7.1).
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.users.enums import PlatformRole

DisplayName = Annotated[str, Field(min_length=1, max_length=100)]


class UserRead(BaseModel):
    """Public representation of a user account.

    ``platform_role`` is the platform axis only. A caller's standing inside a
    company is read from the workspaces API, so no response can be mistaken for
    a grant of tenant access (architecture doc section 9).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    # Plain ``str`` on output: reads must never fail because a stored value no
    # longer satisfies a validator (``EmailStr`` still guards registration).
    email: str
    display_name: str
    platform_role: PlatformRole
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    """Paginated collection envelope (architecture doc section 6/7)."""

    items: list[UserRead]
    total: int
    page: int
    page_size: int
    pages: int


class UserUpdate(BaseModel):
    """Partial profile update; only supplied fields are changed."""

    model_config = ConfigDict(str_strip_whitespace=True)

    display_name: DisplayName | None = None


class PlatformRoleUpdate(BaseModel):
    """Platform-role change, restricted to operators by the router."""

    platform_role: PlatformRole
