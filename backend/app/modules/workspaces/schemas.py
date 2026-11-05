"""Pydantic request/response contracts for the workspaces module.

SQLAlchemy models are never exposed directly, and no contract carries another
tenant's data: ``my_role`` and ``capabilities`` are included so the frontend can
decide what to render without ever being the thing that decides (architecture doc
sections 7 and 9).
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.workspaces.enums import (
    InviteStatus,
    WorkspaceAction,
    WorkspaceKind,
    WorkspaceRole,
    WorkspaceStatus,
)

WorkspaceName = Annotated[str, Field(min_length=1, max_length=120)]

#: A tenant address: lowercase, starts and ends alphanumeric, 3-63 characters.
SLUG_PATTERN = r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])?$"

#: What an invitation may grant. Ownership is never handed out by invitation: it
#: is transferred by an existing owner, so a compromised address cannot make
#: itself the head of a company.
InvitableRole = Literal[WorkspaceRole.MEMBER, WorkspaceRole.ADMIN]


class WorkspaceCreate(BaseModel):
    """Open a company tenant."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: WorkspaceName
    slug: Annotated[str, Field(min_length=3, max_length=63, pattern=SLUG_PATTERN)]


class WorkspaceUpdate(BaseModel):
    """Rename a tenant.

    The slug is deliberately absent: it is the address people have bookmarked,
    and changing it is an administrative act with different consequences from
    fixing a typo in a name.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    name: WorkspaceName


class MemberRoleUpdate(BaseModel):
    """Change a member's role inside one tenant."""

    role: WorkspaceRole


class InviteCreate(BaseModel):
    """Open a tenant to an address. Delivery is a later concern, not a model one.

    ``role`` is a ``Literal`` rather than the full enum: the contract itself
    cannot express an invited owner, so escalation is not a rule the service has
    to remember to enforce.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    role: InvitableRole = WorkspaceRole.MEMBER


class WorkspaceRead(BaseModel):
    """A tenant as its member sees it."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: WorkspaceKind
    name: str
    slug: str | None
    status: WorkspaceStatus
    created_at: datetime
    updated_at: datetime


class WorkspaceWithRoleRead(WorkspaceRead):
    """A tenant plus the caller's standing in it.

    ``capabilities`` is what the access policy allows this caller right now ---
    for example, a suspended company drops ``edit_content`` for everyone. It is a
    rendering hint computed by the backend; every request is still re-checked.
    """

    my_role: WorkspaceRole
    capabilities: list[WorkspaceAction]


class MemberRead(BaseModel):
    """One membership, with just enough of the account to recognise it."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    email: str
    display_name: str
    role: WorkspaceRole
    joined_at: datetime


class InviteRead(BaseModel):
    """An invitation as the tenant sees it."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    role: WorkspaceRole
    status: InviteStatus
    created_at: datetime
    resolved_at: datetime | None


class InvitationRead(BaseModel):
    """An invitation as its addressee sees it: the tenant, and who opened it."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    workspace_name: str
    workspace_slug: str | None
    workspace_status: WorkspaceStatus
    # Decided by the access policy: a suspended company admits nobody, so the
    # offer stays visible but cannot be claimed until the company is restored.
    can_accept: bool
    role: WorkspaceRole
    invited_by_name: str | None
    created_at: datetime


class WorkspaceListResponse(BaseModel):
    """Paginated collection envelope (architecture doc sections 6 and 7)."""

    items: list[WorkspaceWithRoleRead]
    total: int
    page: int
    page_size: int
    pages: int


class MemberListResponse(BaseModel):
    items: list[MemberRead]
    total: int
    page: int
    page_size: int
    pages: int


class InviteListResponse(BaseModel):
    items: list[InviteRead]
    total: int
    page: int
    page_size: int
    pages: int


class InvitationListResponse(BaseModel):
    """The caller's pending invitations. Not paginated: a person is invited by
    a handful of companies, and every row is actionable on the same screen."""

    items: list[InvitationRead]


class TenantAdminRead(WorkspaceRead):
    """A tenant in the platform console: identity, lifecycle, head count.

    Extends the member-facing shape with two operator columns. An operator sees
    how many accounts belong and why the tenant was switched off; they do not see
    task titles, descriptions, comments, or member email addresses from here, and
    this type is where that boundary is written down rather than enforced by
    forgetting to select a column (architecture doc section 9).
    """

    member_count: int
    operator_note: str | None


class TenantAdminListResponse(BaseModel):
    items: list[TenantAdminRead]
    total: int
    page: int
    page_size: int
    pages: int


class SuspensionUpdate(BaseModel):
    """Why a tenant is suspended or restored, for the operator record."""

    model_config = ConfigDict(str_strip_whitespace=True)

    note: Annotated[str | None, Field(default=None, max_length=500)]
