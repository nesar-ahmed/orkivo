"""Application service for workspaces: tenancy, membership and invitations.

This module owns the single rule the rest of the product depends on: **access to
a tenant comes from a ``workspace_members`` row, read from the database on every
request**. Nothing in a token, a URL or a frontend decision grants it
(architecture doc sections 5 and 9).

Capabilities, enforced here rather than merely displayed in the UI:

====================================  ==========  ========  ======  ============
Operation                             owner       admin     member  not a member
====================================  ==========  ========  ======  ============
Read the tenant and its people         yes        yes       yes     404
Rename the tenant                     yes        yes        --      404
Invite, revoke, list invitations      yes        yes        --      404
Remove a member                       yes        yes (1)    --      404
Change roles                          yes         --        --      404
====================================  ==========  ========  ======  ============

(1) an admin may remove members and other admins, never an owner.

A non-member is answered with *not found*, never *forbidden*: confirming that a
tenant exists would make the API an oracle for other companies' names.
"""

import math
import uuid
from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.users.models import User
from app.modules.users.service import normalize_email
from app.modules.workspaces import repository
from app.modules.workspaces.enums import (
    InviteStatus,
    WorkspaceKind,
    WorkspaceRole,
    WorkspaceStatus,
)
from app.modules.workspaces.exceptions import (
    AlreadyInvitedError,
    AlreadyMemberError,
    InviteNotPendingError,
    LastOwnerError,
    PersonalWorkspaceError,
    WorkspaceNotFoundError,
    WorkspaceRoleNotAllowedError,
    WorkspaceSlugInUseError,
    WorkspaceSuspendedError,
)
from app.modules.workspaces.models import Workspace, WorkspaceInvite, WorkspaceMember
from app.modules.workspaces.schemas import InviteCreate, WorkspaceCreate, WorkspaceUpdate
from app.shared.time import utc_now

#: Addresses a company may not take. Path-routed tenancy means a slug is a URL,
#: so letting a tenant claim ``admin`` or ``platform`` is how a customer ends up
#: impersonating its host.
RESERVED_SLUGS = frozenset(
    {
        "admin",
        "api",
        "app",
        "auth",
        "dashboard",
        "invite",
        "login",
        "logout",
        "platform",
        "register",
        "settings",
        "support",
        "workspace",
        "workspaces",
    }
)

_MANAGE_ROLES = (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)


class WorkspaceService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # --- creation ----------------------------------------------------------
    def create_personal_for(self, user: User, *, commit: bool = True) -> Workspace:
        """Every account gets a private tenant at registration.

        This is what makes "individual" and "company" the same thing to the
        authorization code: personal work is work in a tenant that happens to
        have exactly one member, so there is no second query path to get wrong.

        ``commit=False`` is for registration, where the account and this tenant
        are one transaction and ``AuthService`` owns the boundary
        (architecture doc section 6.2).
        """
        workspace = Workspace(
            kind=WorkspaceKind.PERSONAL,
            name=f"{user.display_name}'s workspace",
            slug=None,
        )
        repository.add(self._session, workspace)
        repository.add_member(
            self._session,
            WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=WorkspaceRole.OWNER),
        )
        if commit:
            self._commit()
        return workspace

    def create_team(self, data: WorkspaceCreate, *, actor: User) -> Workspace:
        """Open a company. The creator becomes its owner, unconditionally."""
        slug = data.slug.strip().lower()
        if slug in RESERVED_SLUGS:
            raise WorkspaceSlugInUseError(f"'{slug}' is reserved for the platform.")

        workspace = Workspace(kind=WorkspaceKind.TEAM, name=data.name, slug=slug)
        try:
            repository.add(self._session, workspace)
        except IntegrityError:
            self._session.rollback()
            # The slug is the only unique column on this table.
            raise WorkspaceSlugInUseError from None

        repository.add_member(
            self._session,
            WorkspaceMember(workspace_id=workspace.id, user_id=actor.id, role=WorkspaceRole.OWNER),
        )
        self._commit()
        return workspace

    # --- reading -----------------------------------------------------------
    def list_for_user(
        self, user_id: uuid.UUID, *, page: int = 1, page_size: int = 20
    ) -> tuple[Sequence[tuple[Workspace, WorkspaceRole]], int, int]:
        rows, total = repository.list_for_user(
            self._session, user_id, page=page, page_size=page_size
        )
        return rows, total, _pages(total, page, page_size)

    def get_readable(self, workspace_id: uuid.UUID, *, actor: User) -> Workspace:
        """The tenant, if the caller belongs to it. Outsiders get 404."""
        workspace, _member = self._membership(workspace_id, actor=actor)
        return workspace

    def read_with_role(
        self, workspace_id: uuid.UUID, *, actor: User
    ) -> tuple[Workspace, WorkspaceRole]:
        """The tenant and the caller's role, in one membership resolution.

        Returned together because the role is never optional once the tenant is
        readable: asking for it separately invites a second query whose answer
        could differ from the first.
        """
        workspace, member = self._membership(workspace_id, actor=actor)
        return workspace, member.role

    def require_role(
        self, workspace_id: uuid.UUID, *, actor: User, allowed: Sequence[WorkspaceRole]
    ) -> Workspace:
        """The tenant, requiring one of ``allowed`` roles. Outsiders get 404."""
        workspace, member = self._membership(workspace_id, actor=actor)
        if member.role not in allowed:
            raise WorkspaceRoleNotAllowedError
        return workspace

    def member_role(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> WorkspaceRole | None:
        member = repository.get_member(self._session, workspace_id, user_id)
        return member.role if member is not None else None

    def rename(self, workspace_id: uuid.UUID, data: WorkspaceUpdate, *, actor: User) -> Workspace:
        workspace = self.require_role(workspace_id, actor=actor, allowed=_MANAGE_ROLES)
        workspace.name = data.name
        self._session.flush()
        self._commit()
        return workspace

    # --- members -----------------------------------------------------------
    def list_members(
        self, workspace_id: uuid.UUID, *, actor: User, page: int = 1, page_size: int = 20
    ) -> tuple[Sequence[tuple[WorkspaceMember, User]], int, int]:
        self.get_readable(workspace_id, actor=actor)
        rows, total = repository.list_members(
            self._session, workspace_id, page=page, page_size=page_size
        )
        return rows, total, _pages(total, page, page_size)

    def remove_member(
        self, workspace_id: uuid.UUID, member_user_id: uuid.UUID, *, actor: User
    ) -> None:
        """Remove someone, or let an account leave a company.

        Two invariants: only an owner may remove an owner, and the last owner may
        not go. A tenant without an owner is a company nobody can administer,
        visible only to an operator.
        """
        workspace, acting = self._membership(workspace_id, actor=actor)
        target = repository.get_member(self._session, workspace.id, member_user_id)
        if target is None:
            # Same shape as "no such tenant": the membership is not confirmable.
            raise WorkspaceNotFoundError(workspace.id)

        leaving_alone = acting.id == target.id
        if target.role is WorkspaceRole.OWNER:
            if not leaving_alone and acting.role is not WorkspaceRole.OWNER:
                raise WorkspaceRoleNotAllowedError
            if repository.count_owners(self._session, workspace.id) <= 1:
                raise LastOwnerError
        elif not leaving_alone and acting.role not in _MANAGE_ROLES:
            raise WorkspaceRoleNotAllowedError

        repository.remove_member(self._session, target)
        self._commit()

    def change_member_role(
        self,
        workspace_id: uuid.UUID,
        member_user_id: uuid.UUID,
        *,
        role: WorkspaceRole,
        actor: User,
    ) -> tuple[WorkspaceMember, User]:
        """Move someone between owner, admin and member. Owners only.

        Ownership can be granted here (that is how a company gets a second
        accountable head) but never by invitation, and the last owner cannot be
        demoted out of existence.
        """
        workspace = self.require_role(workspace_id, actor=actor, allowed=(WorkspaceRole.OWNER,))
        target = repository.get_member(self._session, workspace.id, member_user_id)
        if target is None:
            raise WorkspaceNotFoundError(workspace.id)

        if (
            target.role is WorkspaceRole.OWNER
            and role is not WorkspaceRole.OWNER
            and repository.count_owners(self._session, workspace.id) <= 1
        ):
            raise LastOwnerError

        target.role = role
        self._session.flush()
        self._commit()
        changed = repository.get_member_with_user(self._session, workspace.id, member_user_id)
        if changed is None:  # unreachable: the row was just written
            raise WorkspaceNotFoundError(workspace.id)
        return changed

    def count_members(self, workspace_id: uuid.UUID) -> int:
        """Head count for the console and the people screen. Never a list."""
        return repository.count_members(self._session, workspace_id)

    # --- invitations -------------------------------------------------------
    def invite(
        self, workspace_id: uuid.UUID, data: InviteCreate, *, actor: User
    ) -> WorkspaceInvite:
        """Open the tenant to an address: no delivery, no account required.

        The row is exactly what a mail transport would later send, which is why
        adding email does not change this model. Re-invoking an address that
        declined or was revoked reopens that row instead of stacking duplicates,
        and an invitation can only ever offer ``member`` or ``admin``.
        """
        workspace = self.require_role(workspace_id, actor=actor, allowed=_MANAGE_ROLES)
        if workspace.kind is WorkspaceKind.PERSONAL:
            raise PersonalWorkspaceError
        if workspace.status is not WorkspaceStatus.ACTIVE:
            raise WorkspaceSuspendedError

        email = normalize_email(data.email)
        if repository.get_member_by_email(self._session, workspace.id, email) is not None:
            raise AlreadyMemberError

        existing = repository.get_invite_by_workspace_and_email(self._session, workspace.id, email)
        if existing is not None:
            if existing.status is InviteStatus.PENDING:
                raise AlreadyInvitedError
            existing.status = InviteStatus.PENDING
            existing.role = data.role
            existing.invited_by = actor.id
            existing.resolved_at = None
            self._session.flush()
            self._commit()
            return existing

        invite = WorkspaceInvite(
            workspace_id=workspace.id,
            email=email,
            role=data.role,
            status=InviteStatus.PENDING,
            invited_by=actor.id,
        )
        repository.add_invite(self._session, invite)
        self._commit()
        return invite

    def list_invites(
        self, workspace_id: uuid.UUID, *, actor: User, page: int = 1, page_size: int = 20
    ) -> tuple[Sequence[WorkspaceInvite], int, int]:
        self.require_role(workspace_id, actor=actor, allowed=_MANAGE_ROLES)
        items, total = repository.list_invites(
            self._session, workspace_id, page=page, page_size=page_size
        )
        return items, total, _pages(total, page, page_size)

    def revoke_invite(
        self, workspace_id: uuid.UUID, invite_id: uuid.UUID, *, actor: User
    ) -> WorkspaceInvite:
        self.require_role(workspace_id, actor=actor, allowed=_MANAGE_ROLES)
        invite = repository.get_invite(self._session, invite_id)
        if invite is None or invite.workspace_id != workspace_id:
            # Never confirm which tenant an invitation belongs to.
            raise InviteNotPendingError
        if invite.status is not InviteStatus.PENDING:
            raise InviteNotPendingError

        invite.status = InviteStatus.REVOKED
        invite.resolved_at = utc_now()
        self._session.flush()
        self._commit()
        return invite

    def list_my_invitations(
        self, *, actor: User
    ) -> Sequence[tuple[WorkspaceInvite, Workspace, User | None]]:
        """Invitations addressed to this account's email address.

        Matching the address *is* the claim rule: it is what a delivered link
        would prove, so accepting works identically with or without mail.
        """
        return repository.list_pending_for_email(self._session, actor.email)

    def accept_invitation(self, invite_id: uuid.UUID, *, actor: User) -> Workspace:
        """Claim an invitation and join, with the role it offered.

        The address must match, the row must still be pending, and the tenant
        must be active: a suspended company gains no new members while it is
        switched off.
        """
        invite = repository.get_invite(self._session, invite_id)
        if invite is None or invite.status is not InviteStatus.PENDING:
            raise InviteNotPendingError
        if invite.email != actor.email:
            # Not yours to claim --- without confirming the address exists.
            raise InviteNotPendingError

        workspace = repository.get_by_id(self._session, invite.workspace_id)
        if workspace is None:
            raise InviteNotPendingError
        if workspace.status is not WorkspaceStatus.ACTIVE:
            raise WorkspaceSuspendedError
        if repository.get_member(self._session, workspace.id, actor.id) is not None:
            raise AlreadyMemberError

        repository.add_member(
            self._session,
            WorkspaceMember(workspace_id=workspace.id, user_id=actor.id, role=invite.role),
        )
        invite.status = InviteStatus.ACCEPTED
        invite.resolved_at = utc_now()
        self._commit()
        return workspace

    def decline_invitation(self, invite_id: uuid.UUID, *, actor: User) -> WorkspaceInvite:
        invite = repository.get_invite(self._session, invite_id)
        if (
            invite is None
            or invite.status is not InviteStatus.PENDING
            or invite.email != actor.email
        ):
            raise InviteNotPendingError

        invite.status = InviteStatus.DECLINED
        invite.resolved_at = utc_now()
        self._session.flush()
        self._commit()
        return invite

    # --- platform lifecycle ------------------------------------------------
    def set_suspended(
        self, workspace_id: uuid.UUID, *, suspended: bool, note: str | None
    ) -> Workspace:
        """Operator switch. Members keep their rows; the tenant stops working.

        Deliberately not a membership change: suspension is reversible and must
        not destroy a company's history or its people's place in it.
        """
        workspace = repository.get_by_id(self._session, workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError(workspace_id)
        workspace.status = WorkspaceStatus.SUSPENDED if suspended else WorkspaceStatus.ACTIVE
        if note is not None:
            workspace.operator_note = note
        self._session.flush()
        self._commit()
        return workspace

    def list_tenants(
        self,
        *,
        search: str | None = None,
        kind: WorkspaceKind | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[tuple[Workspace, int]], int, int]:
        """Console listing: counts and metadata only, never content."""
        rows, total = repository.list_tenants(
            self._session, search=search, kind=kind, page=page, page_size=page_size
        )
        return rows, total, _pages(total, page, page_size)

    # --- helpers -----------------------------------------------------------
    def _membership(
        self, workspace_id: uuid.UUID, *, actor: User
    ) -> tuple[Workspace, WorkspaceMember]:
        """Resolve tenant + caller's membership, or the not-found shape.

        Both failures answer identically on purpose: a caller who is not in a
        tenant must not learn that it exists.
        """
        workspace = repository.get_by_id(self._session, workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError(workspace_id)
        member = repository.get_member(self._session, workspace.id, actor.id)
        if member is None:
            raise WorkspaceNotFoundError(workspace_id)
        return workspace, member

    def _commit(self) -> None:
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise


def _pages(total: int, page: int, page_size: int) -> int:
    """Page count for the collection envelope."""
    return math.ceil(total / page_size) if total else 0
