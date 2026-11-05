"""Tenant access control: the one place that decides who may do what in a workspace.

Every feature that stores something inside a tenant --- tasks today, projects and
comments next --- asks this module, and only this module, whether the caller may
touch it. The rules are a table rather than ``if`` statements spread over
services, so changing a decision (for instance what suspension means) is one
edit that every feature inherits (architecture doc sections 5 and 9).

Four rules hold for every action:

* **Membership is the only grant.** Access comes from a ``workspace_members`` row
  read from the database on this request. A platform role, a token claim, a URL
  or a frontend decision grants nothing.
* **Outsiders see nothing.** A caller who is not a member receives the *not
  found* shape --- the tenant's own, or the resource's via
  :meth:`WorkspaceAccessPolicy.require_for_content` --- identical to an id that
  does not exist, so the API is never an oracle for other companies' data.
* **Members are told why.** Once membership is established, a refusal is a 403
  (wrong role, or the tenant is suspended) or a 409 (the action makes no sense
  in a private workspace): the caller already knows the tenant exists, and a
  clear reason is more useful than a fake 404.
* **A suspended company is in view mode.** Every member keeps reading everything
  they could read before --- tasks, people, invitations --- and nothing at all
  changes until an operator restores it. A private workspace is never suspended;
  an individual is stopped by disabling the *account* instead
  (:func:`can_be_suspended`).

====================  ==============  ============  ===========================
Action                Roles           Private ws    While the tenant is suspended
====================  ==============  ============  ===========================
read                  every member    yes           allowed (view mode)
edit_content          every member    yes           refused
leave                 every member    no            refused
view_invites          owner, admin    no            allowed (view mode)
manage                owner, admin    yes (rename)  refused
invite                owner, admin    no            refused
change_roles          owner           no            refused
====================  ==============  ============  ===========================
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from sqlalchemy.orm import Session

from app.modules.users.models import User
from app.modules.workspaces import repository
from app.modules.workspaces.enums import (
    WorkspaceAction,
    WorkspaceKind,
    WorkspaceRole,
    WorkspaceStatus,
)
from app.modules.workspaces.exceptions import (
    PersonalWorkspaceError,
    WorkspaceNotFoundError,
    WorkspaceRoleNotAllowedError,
    WorkspaceSuspendedError,
)
from app.modules.workspaces.models import Workspace, WorkspaceMember


@dataclass(frozen=True)
class AccessRule:
    """Who may perform one action, where, and whether suspension switches it off.

    ``in_personal`` is False for actions that only make sense among several
    people: a private workspace has exactly one member, forever.
    """

    roles: frozenset[WorkspaceRole]
    while_suspended: bool
    in_personal: bool = True


_EVERY_MEMBER = frozenset(WorkspaceRole)
_MANAGERS = frozenset({WorkspaceRole.OWNER, WorkspaceRole.ADMIN})

#: The policy. Read-only to the rest of the program: a rule is changed here, in
#: review, and never patched at runtime by a feature that wants an exception.
#:
#: Suspension is a product decision recorded here rather than in any one
#: feature: a suspended company is in *view mode*. Every member --- whatever
#: their role --- keeps seeing what they saw before, and nothing changes: no
#: task edits, no rename, no invitations, no role changes, no removals and no
#: leaving, until an operator restores it. Only the rows marked
#: ``while_suspended=True`` are reads.
ACCESS_RULES: Mapping[WorkspaceAction, AccessRule] = MappingProxyType(
    {
        WorkspaceAction.READ: AccessRule(roles=_EVERY_MEMBER, while_suspended=True),
        WorkspaceAction.EDIT_CONTENT: AccessRule(roles=_EVERY_MEMBER, while_suspended=False),
        WorkspaceAction.LEAVE: AccessRule(
            roles=_EVERY_MEMBER, while_suspended=False, in_personal=False
        ),
        WorkspaceAction.VIEW_INVITES: AccessRule(
            roles=_MANAGERS, while_suspended=True, in_personal=False
        ),
        WorkspaceAction.MANAGE: AccessRule(roles=_MANAGERS, while_suspended=False),
        WorkspaceAction.INVITE: AccessRule(
            roles=_MANAGERS, while_suspended=False, in_personal=False
        ),
        WorkspaceAction.CHANGE_ROLES: AccessRule(
            roles=frozenset({WorkspaceRole.OWNER}), while_suspended=False, in_personal=False
        ),
    }
)


def is_allowed(
    action: WorkspaceAction,
    *,
    role: WorkspaceRole,
    status: WorkspaceStatus,
    kind: WorkspaceKind = WorkspaceKind.TEAM,
) -> bool:
    """Pure evaluation of one rule, with no database access and no exception."""
    rule = ACCESS_RULES[action]
    if role not in rule.roles:
        return False
    if kind is WorkspaceKind.PERSONAL and not rule.in_personal:
        return False
    return status is WorkspaceStatus.ACTIVE or rule.while_suspended


def allowed_actions(
    *,
    role: WorkspaceRole,
    status: WorkspaceStatus,
    kind: WorkspaceKind = WorkspaceKind.TEAM,
) -> list[WorkspaceAction]:
    """Every action a member with ``role`` may perform in this kind of tenant now.

    Ordered as the enum declares them, so the API response is stable.
    """
    return [
        action
        for action in WorkspaceAction
        if is_allowed(action, role=role, status=status, kind=kind)
    ]


def admits_new_members(workspace: Workspace) -> bool:
    """Whether anyone may *join* this tenant right now.

    Joining happens before membership exists, so it is not a rule in the table
    above; it is kept here so that everything suspension means lives in one file.
    """
    return workspace.status is WorkspaceStatus.ACTIVE


def can_be_suspended(workspace: Workspace) -> bool:
    """Whether an operator may suspend this tenant.

    Only companies. A private workspace belongs to one person, so the lever for
    an individual is disabling their account, which ends every session too.
    Restoring stays possible for any tenant, so nothing can get stuck.
    """
    return workspace.kind is WorkspaceKind.TEAM


def enforce(access: "WorkspaceAccess", action: WorkspaceAction) -> None:
    """Raise the member-facing refusal if ``access`` does not cover ``action``.

    Checked in a fixed order --- role, then workspace kind, then suspension --- so
    the same request always gets the same reason.
    """
    rule = ACCESS_RULES[action]
    if access.member.role not in rule.roles:
        raise WorkspaceRoleNotAllowedError
    if access.workspace.kind is WorkspaceKind.PERSONAL and not rule.in_personal:
        raise PersonalWorkspaceError
    if access.workspace.status is not WorkspaceStatus.ACTIVE and not rule.while_suspended:
        raise WorkspaceSuspendedError


@dataclass(frozen=True)
class WorkspaceAccess:
    """A resolved, authorized view of one tenant for one caller."""

    workspace: Workspace
    member: WorkspaceMember

    @property
    def role(self) -> WorkspaceRole:
        return self.member.role

    def allows(self, action: WorkspaceAction) -> bool:
        return is_allowed(
            action,
            role=self.member.role,
            status=self.workspace.status,
            kind=self.workspace.kind,
        )

    def require(self, action: WorkspaceAction) -> None:
        """Enforce a second action on an already-resolved membership."""
        enforce(self, action)

    @property
    def actions(self) -> list[WorkspaceAction]:
        return allowed_actions(
            role=self.member.role, status=self.workspace.status, kind=self.workspace.kind
        )


class WorkspaceAccessPolicy:
    """Resolve a caller's membership and enforce :data:`ACCESS_RULES`.

    Holds no state beyond the request's session, so every service that needs it
    builds its own --- there is nothing to keep in sync between them.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def require(
        self,
        workspace_id: uuid.UUID,
        *,
        actor: User,
        action: WorkspaceAction = WorkspaceAction.READ,
    ) -> WorkspaceAccess:
        """The tenant, if ``actor`` may perform ``action`` in it.

        Raises ``WorkspaceNotFoundError`` for a missing tenant *and* for one the
        caller is not in --- the two are deliberately indistinguishable --- and a
        403-shaped error when a member's role or the tenant's status refuses.
        """
        workspace = repository.get_by_id(self._session, workspace_id)
        return self._authorize(workspace, workspace_id, actor=actor, action=action)

    def require_slug(
        self,
        slug: str,
        *,
        actor: User,
        action: WorkspaceAction = WorkspaceAction.READ,
    ) -> WorkspaceAccess:
        """Same as :meth:`require`, addressed by the company's URL name."""
        workspace = repository.get_by_slug(self._session, slug.strip().lower())
        # A random id keeps the error's shape without echoing anything back.
        return self._authorize(workspace, uuid.uuid4(), actor=actor, action=action)

    def require_for_content(
        self,
        workspace_id: uuid.UUID,
        *,
        actor: User,
        action: WorkspaceAction,
        hidden_as: Exception,
    ) -> WorkspaceAccess:
        """Authorize access to something stored *inside* a tenant.

        A caller outside the tenant receives ``hidden_as`` --- the resource's own
        not-found error --- so "this task is in a company you are not in" answers
        exactly like "this task does not exist". Members still get the precise
        403 for a role or suspension refusal. Every feature that stores content
        in a tenant should reach its rows through this method.
        """
        try:
            return self.require(workspace_id, actor=actor, action=action)
        except WorkspaceNotFoundError:
            raise hidden_as from None

    def require_personal(
        self, *, actor: User, action: WorkspaceAction = WorkspaceAction.READ
    ) -> WorkspaceAccess:
        """The caller's own private tenant.

        Registration creates it with the account, so its absence is a data fault
        rather than a request error; it still answers with the not-found shape
        instead of inventing a new one.
        """
        workspace = repository.get_personal_for(self._session, actor.id)
        if workspace is None:
            raise WorkspaceNotFoundError(uuid.uuid4())
        return self._authorize(workspace, workspace.id, actor=actor, action=action)

    def _authorize(
        self,
        workspace: Workspace | None,
        requested_id: uuid.UUID,
        *,
        actor: User,
        action: WorkspaceAction,
    ) -> WorkspaceAccess:
        if workspace is None:
            raise WorkspaceNotFoundError(requested_id)
        member = repository.get_member(self._session, workspace.id, actor.id)
        if member is None:
            # Same shape as "no such tenant": membership is never confirmable.
            raise WorkspaceNotFoundError(requested_id)

        access = WorkspaceAccess(workspace=workspace, member=member)
        enforce(access, action)
        return access
