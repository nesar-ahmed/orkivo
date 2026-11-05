"""HTTP routes for workspaces, plus the platform console over tenants.

Routes parse and validate, then hand the *acting user* to the service, so
membership and role are resolved from the database rather than from the path or
the token (architecture doc sections 4.1 and 9). No route here reaches into the
service's session.

One ordering rule matters. ``/workspaces/invitations`` and
``/workspaces/by-slug/{slug}`` are declared before ``/workspaces/{workspace_id}``,
because a UUID path parameter would otherwise swallow the literal segment and
answer 422 instead of the intended route.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from app.modules.auth.dependencies import CurrentUser, OperatorUser
from app.modules.users.models import User
from app.modules.workspaces.access import WorkspaceAccess, admits_new_members, allowed_actions
from app.modules.workspaces.dependencies import WorkspaceServiceDep
from app.modules.workspaces.enums import WorkspaceKind, WorkspaceRole
from app.modules.workspaces.models import Workspace, WorkspaceMember
from app.modules.workspaces.schemas import (
    SLUG_PATTERN,
    InvitationListResponse,
    InvitationRead,
    InviteCreate,
    InviteListResponse,
    InviteRead,
    MemberListResponse,
    MemberRead,
    MemberRoleUpdate,
    SuspensionUpdate,
    TenantAdminListResponse,
    TenantAdminRead,
    WorkspaceCreate,
    WorkspaceListResponse,
    WorkspaceRead,
    WorkspaceUpdate,
    WorkspaceWithRoleRead,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
platform_router = APIRouter(prefix="/platform/workspaces", tags=["platform"])

PageParam = Annotated[int, Query(ge=1)]
PageSizeParam = Annotated[int, Query(ge=1, le=100)]
WorkspaceId = Annotated[uuid.UUID, Path(description="Tenant identifier.")]
WorkspaceSlug = Annotated[
    str, Path(min_length=3, max_length=63, pattern=SLUG_PATTERN, description="Company address.")
]
MemberUserId = Annotated[uuid.UUID, Path(description="Account to act on.")]


def _member_read(member: WorkspaceMember, account: User) -> MemberRead:
    """One membership row plus its account, in the shape people expect."""
    return MemberRead(
        id=member.id,
        user_id=account.id,
        email=account.email,
        display_name=account.display_name,
        role=member.role,
        joined_at=member.joined_at,
    )


def _workspace_with_role(workspace: Workspace, role: WorkspaceRole) -> WorkspaceWithRoleRead:
    """The tenant shape plus the caller's standing in it.

    Built from a validated ``WorkspaceRead`` rather than by handing the subclass
    the ORM object: the role lives on the membership row, so validating it against
    the workspace alone would fail on a required field.
    """
    base = WorkspaceRead.model_validate(workspace)
    return WorkspaceWithRoleRead(
        **base.model_dump(),
        my_role=role,
        capabilities=allowed_actions(role=role, status=workspace.status, kind=workspace.kind),
    )


def _from_access(access: WorkspaceAccess) -> WorkspaceWithRoleRead:
    return _workspace_with_role(access.workspace, access.role)


def _tenant_row(workspace: Workspace, member_count: int) -> TenantAdminRead:
    """The console row for a tenant: the member-visible fields plus the two
    operator columns, with the head count supplied by the caller."""
    base = WorkspaceRead.model_validate(workspace)
    return TenantAdminRead(
        **base.model_dump(),
        member_count=member_count,
        operator_note=workspace.operator_note,
    )


# --- my tenants ------------------------------------------------------------
@router.get("", response_model=WorkspaceListResponse)
def list_my_workspaces(
    user: CurrentUser,
    service: WorkspaceServiceDep,
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
) -> WorkspaceListResponse:
    """Every tenant the caller belongs to, with the role held in each."""
    rows, total, pages = service.list_for_user(user.id, page=page, page_size=page_size)
    return WorkspaceListResponse(
        items=[_workspace_with_role(workspace, role) for workspace, role in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreate, user: CurrentUser, service: WorkspaceServiceDep
) -> WorkspaceRead:
    """Open a company. The caller becomes its owner."""
    return WorkspaceRead.model_validate(service.create_team(payload, actor=user))


# --- the caller's own invitations -------------------------------------------
# Declared before ``/{workspace_id}`` so the literal path wins.
@router.get("/invitations", response_model=InvitationListResponse)
def list_my_invitations(user: CurrentUser, service: WorkspaceServiceDep) -> InvitationListResponse:
    """Invitations addressed to this account's email, for the profile screen."""
    rows = service.list_my_invitations(actor=user)
    return InvitationListResponse(
        items=[
            InvitationRead(
                id=invite.id,
                workspace_id=workspace.id,
                workspace_name=workspace.name,
                workspace_slug=workspace.slug,
                workspace_status=workspace.status,
                can_accept=admits_new_members(workspace),
                role=invite.role,
                invited_by_name=inviter.display_name if inviter is not None else None,
                created_at=invite.created_at,
            )
            for invite, workspace, inviter in rows
        ]
    )


@router.post("/invitations/{invite_id}/accept", response_model=WorkspaceWithRoleRead)
def accept_invitation(
    invite_id: Annotated[uuid.UUID, Path(description="Invitation to claim.")],
    user: CurrentUser,
    service: WorkspaceServiceDep,
) -> WorkspaceWithRoleRead:
    """Claim an invitation and join, at the role it offered."""
    joined = service.accept_invitation(invite_id, actor=user)
    return _from_access(service.read_access(joined.id, actor=user))


@router.post(
    "/invitations/{invite_id}/decline",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def decline_invitation(
    invite_id: Annotated[uuid.UUID, Path(description="Invitation to turn down.")],
    user: CurrentUser,
    service: WorkspaceServiceDep,
) -> Response:
    """Turn an invitation down. The tenant may open another later."""
    service.decline_invitation(invite_id, actor=user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- one tenant ------------------------------------------------------------
# Declared before ``/{workspace_id}`` so the literal path wins.
@router.get("/by-slug/{slug}", response_model=WorkspaceWithRoleRead)
def read_workspace_by_slug(
    slug: WorkspaceSlug, user: CurrentUser, service: WorkspaceServiceDep
) -> WorkspaceWithRoleRead:
    """A company by its address, for the URLs people share. Members only.

    A slug the caller does not belong to answers exactly like one that was never
    registered, so a URL cannot be used to probe for another company.
    """
    return _from_access(service.read_access_by_slug(slug, actor=user))


@router.get("/{workspace_id}", response_model=WorkspaceWithRoleRead)
def read_workspace(
    workspace_id: WorkspaceId, user: CurrentUser, service: WorkspaceServiceDep
) -> WorkspaceWithRoleRead:
    """A tenant, for its members. Outsiders receive the not-found shape."""
    return _from_access(service.read_access(workspace_id, actor=user))


@router.patch("/{workspace_id}", response_model=WorkspaceRead)
def rename_workspace(
    workspace_id: WorkspaceId,
    payload: WorkspaceUpdate,
    user: CurrentUser,
    service: WorkspaceServiceDep,
) -> WorkspaceRead:
    """Rename a tenant. Owner or admin."""
    return WorkspaceRead.model_validate(service.rename(workspace_id, payload, actor=user))


# --- people ----------------------------------------------------------------
@router.get("/{workspace_id}/members", response_model=MemberListResponse)
def list_members(
    workspace_id: WorkspaceId,
    user: CurrentUser,
    service: WorkspaceServiceDep,
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
) -> MemberListResponse:
    """The company's people. Any member may read the list."""
    rows, total, pages = service.list_members(
        workspace_id, actor=user, page=page, page_size=page_size
    )
    return MemberListResponse(
        items=[_member_read(member, account) for member, account in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.patch("/{workspace_id}/members/{member_user_id}/role", response_model=MemberRead)
def change_member_role(
    workspace_id: WorkspaceId,
    member_user_id: MemberUserId,
    payload: MemberRoleUpdate,
    user: CurrentUser,
    service: WorkspaceServiceDep,
) -> MemberRead:
    """Owner, admin or member. Owners only, and never past the last owner."""
    member, account = service.change_member_role(
        workspace_id, member_user_id, role=payload.role, actor=user
    )
    return _member_read(member, account)


@router.delete(
    "/{workspace_id}/members/{member_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def remove_member(
    workspace_id: WorkspaceId,
    member_user_id: MemberUserId,
    user: CurrentUser,
    service: WorkspaceServiceDep,
) -> Response:
    """Remove someone --- or leave, when it is your own account."""
    service.remove_member(workspace_id, member_user_id, actor=user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- invitations -----------------------------------------------------------
@router.get("/{workspace_id}/invites", response_model=InviteListResponse)
def list_invites(
    workspace_id: WorkspaceId,
    user: CurrentUser,
    service: WorkspaceServiceDep,
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
) -> InviteListResponse:
    """Invitation history for this tenant. Owner or admin."""
    items, total, pages = service.list_invites(
        workspace_id, actor=user, page=page, page_size=page_size
    )
    return InviteListResponse(
        items=[InviteRead.model_validate(invite) for invite in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post(
    "/{workspace_id}/invites", response_model=InviteRead, status_code=status.HTTP_201_CREATED
)
def create_invite(
    workspace_id: WorkspaceId,
    payload: InviteCreate,
    user: CurrentUser,
    service: WorkspaceServiceDep,
) -> InviteRead:
    """Open the tenant to an address. Owner or admin, and never a personal space."""
    return InviteRead.model_validate(service.invite(workspace_id, payload, actor=user))


@router.delete(
    "/{workspace_id}/invites/{invite_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def revoke_invite(
    workspace_id: WorkspaceId,
    invite_id: Annotated[uuid.UUID, Path(description="Invitation to close.")],
    user: CurrentUser,
    service: WorkspaceServiceDep,
) -> Response:
    """Close an open invitation."""
    service.revoke_invite(workspace_id, invite_id, actor=user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- platform console (operators) ------------------------------------------
@platform_router.get("", response_model=TenantAdminListResponse)
def list_tenants(
    actor: OperatorUser,
    service: WorkspaceServiceDep,
    search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    kind: Annotated[WorkspaceKind | None, Query()] = None,
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
) -> TenantAdminListResponse:
    """Every tenant: identity, lifecycle and head count --- never their content."""
    rows, total, pages = service.list_tenants(
        search=search, kind=kind, page=page, page_size=page_size
    )
    return TenantAdminListResponse(
        items=[_tenant_row(workspace, member_count) for workspace, member_count in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@platform_router.post("/{workspace_id}/suspend", response_model=TenantAdminRead)
def suspend_tenant(
    workspace_id: WorkspaceId,
    payload: SuspensionUpdate,
    actor: OperatorUser,
    service: WorkspaceServiceDep,
) -> TenantAdminRead:
    """Switch a tenant off. Reversible, and destroys no membership."""
    workspace = service.set_suspended(workspace_id, suspended=True, note=payload.note)
    return _tenant_row(workspace, service.count_members(workspace.id))


@platform_router.post("/{workspace_id}/activate", response_model=TenantAdminRead)
def activate_tenant(
    workspace_id: WorkspaceId,
    payload: SuspensionUpdate,
    actor: OperatorUser,
    service: WorkspaceServiceDep,
) -> TenantAdminRead:
    """Restore a suspended tenant."""
    workspace = service.set_suspended(workspace_id, suspended=False, note=payload.note)
    return _tenant_row(workspace, service.count_members(workspace.id))
