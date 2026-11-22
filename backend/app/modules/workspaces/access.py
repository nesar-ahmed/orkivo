"""Tenant access control: the one place that decides who may do what in a workspace.

Every feature that stores something inside a tenant --- tasks, projects, labels
and comments --- asks this module, and only this module, whether the caller may
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

* **A role grants only what its row says.** Roles rank owner, admin, manager,
  member, viewer, and each action names the roles it admits --- there is no
  "at least admin" arithmetic to get wrong when a role is added.

====================  ==========================  ============  =====================
Action                Roles                       Private ws    While suspended
====================  ==========================  ============  =====================
read                  every member                yes           allowed (view mode)
edit_content          owner, admin, manager,      yes           refused
                      member
comment               owner, admin, manager,      yes           refused
                      member
manage_tasks          owner, admin, manager       yes           refused
manage_projects       owner, admin, manager       yes           refused
manage_labels         owner, admin, manager       yes           refused
manage_automations    owner, admin, manager       no            refused
leave                 every member                no            refused
view_invites          owner, admin                no            allowed (view mode)
manage                owner, admin                yes (rename)  refused
invite                owner, admin                no            refused
change_roles          owner, admin                no            refused
====================  ==========================  ============  =====================

``edit_content`` covers a member's *own* work only; which task is one's own is a
rule about the target, kept by the tasks module (``tasks.permissions``), exactly
as "only its author edits a comment" is kept by the comments module.

Who may be *given* a role is the second table, :data:`GRANTABLE_ROLES`: an owner
grants every role and an admin grants manager, member and viewer. The same table
says whose membership a caller may change or end, so nobody can promote a peer,
demote a superior or remove either --- only an owner makes or touches an owner or
an admin.
"""

import uuid
from collections.abc import Collection, Mapping, Sequence
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
#: Everyone who works here, as opposed to reading along.
_CONTRIBUTORS = frozenset(
    {WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.MANAGER, WorkspaceRole.MEMBER}
)
#: Everyone who runs the work: all of it, whoever created or holds it.
_WORK_MANAGERS = frozenset({WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.MANAGER})
#: Everyone who runs the tenant itself: its name and its people.
_ADMINS = frozenset({WorkspaceRole.OWNER, WorkspaceRole.ADMIN})

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
        WorkspaceAction.EDIT_CONTENT: AccessRule(roles=_CONTRIBUTORS, while_suspended=False),
        WorkspaceAction.COMMENT: AccessRule(roles=_CONTRIBUTORS, while_suspended=False),
        WorkspaceAction.MANAGE_TASKS: AccessRule(roles=_WORK_MANAGERS, while_suspended=False),
        WorkspaceAction.MANAGE_PROJECTS: AccessRule(roles=_WORK_MANAGERS, while_suspended=False),
        WorkspaceAction.MANAGE_LABELS: AccessRule(roles=_WORK_MANAGERS, while_suspended=False),
        # A private workspace has one person in it, and nobody is told about their
        # own action: every rule there would notify no one.
        WorkspaceAction.MANAGE_AUTOMATIONS: AccessRule(
            roles=_WORK_MANAGERS, while_suspended=False, in_personal=False
        ),
        WorkspaceAction.LEAVE: AccessRule(
            roles=_EVERY_MEMBER, while_suspended=False, in_personal=False
        ),
        WorkspaceAction.VIEW_INVITES: AccessRule(
            roles=_ADMINS, while_suspended=True, in_personal=False
        ),
        WorkspaceAction.MANAGE: AccessRule(roles=_ADMINS, while_suspended=False),
        WorkspaceAction.INVITE: AccessRule(roles=_ADMINS, while_suspended=False, in_personal=False),
        WorkspaceAction.CHANGE_ROLES: AccessRule(
            roles=_ADMINS, while_suspended=False, in_personal=False
        ),
    }
)

#: Which roles each role may hand out --- by invitation or by changing someone's
#: role --- and therefore whose role it may change and whose membership it may
#: end. Read-only, like :data:`ACCESS_RULES`.
#:
#: Only an owner grants ``owner`` or ``admin``: an admin cannot create a peer, so
#: a compromised admin account cannot mint more of itself, and it cannot demote
#: or remove another admin or an owner either. Roles without ``invite`` or
#: ``change_roles`` grant nothing. Invitations never offer ``owner`` whatever
#: this says --- their contract cannot express it (``schemas.InvitableRole``).
GRANTABLE_ROLES: Mapping[WorkspaceRole, frozenset[WorkspaceRole]] = MappingProxyType(
    {
        WorkspaceRole.OWNER: frozenset(WorkspaceRole),
        WorkspaceRole.ADMIN: frozenset(
            {WorkspaceRole.MANAGER, WorkspaceRole.MEMBER, WorkspaceRole.VIEWER}
        ),
        WorkspaceRole.MANAGER: frozenset(),
        WorkspaceRole.MEMBER: frozenset(),
        WorkspaceRole.VIEWER: frozenset(),
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


def grantable_roles(
    *,
    role: WorkspaceRole,
    status: WorkspaceStatus,
    kind: WorkspaceKind = WorkspaceKind.TEAM,
) -> list[WorkspaceRole]:
    """The roles a member with ``role`` may hand out in this tenant right now.

    Empty wherever the caller may neither invite nor change roles --- a private
    workspace, a suspended company, or a role that grants nothing --- so the API
    response never offers a choice the next request would refuse. Ordered as the
    enum declares them (rank order).
    """
    if not (
        is_allowed(WorkspaceAction.INVITE, role=role, status=status, kind=kind)
        or is_allowed(WorkspaceAction.CHANGE_ROLES, role=role, status=status, kind=kind)
    ):
        return []
    return [granted for granted in WorkspaceRole if granted in GRANTABLE_ROLES[role]]


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

    def may_grant(self, role: WorkspaceRole) -> bool:
        """Whether this caller's role may hand out ``role`` (:data:`GRANTABLE_ROLES`).

        The role half only: the caller must also hold ``invite``, ``change_roles``
        or ``manage`` for the operation at hand, which is what refuses a private
        workspace or a suspended company.
        """
        return role in GRANTABLE_ROLES[self.member.role]

    @property
    def actions(self) -> list[WorkspaceAction]:
        return allowed_actions(
            role=self.member.role, status=self.workspace.status, kind=self.workspace.kind
        )

    @property
    def grantable_roles(self) -> list[WorkspaceRole]:
        return grantable_roles(
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

    def readable(self, *, actor: User) -> Sequence[WorkspaceAccess]:
        """Every tenant ``actor`` may read right now, with the access it grants.

        For content read *across* tenants at once --- a person's own tasks in every
        workspace they are in. The same rule as :meth:`require` with ``read``,
        applied to each membership, so there is still exactly one place that
        decides who may read what: a tenant missing from this answer is one the
        caller could not open on its own either.
        """
        accesses = [
            WorkspaceAccess(workspace=workspace, member=member)
            for workspace, member in repository.list_memberships(self._session, actor.id)
        ]
        return [access for access in accesses if access.allows(WorkspaceAction.READ)]

    def members_among(
        self, workspace_id: uuid.UUID, user_ids: Collection[uuid.UUID]
    ) -> Mapping[uuid.UUID, User]:
        """Which of these accounts belong to the tenant right now, by id.

        For content that *points at* people --- a task's assignee today, the
        people a comment mentions next. It authorizes nobody: the caller must
        already hold access to ``workspace_id`` through :meth:`require` or
        :meth:`require_for_content`. An id missing from the answer is either not a
        member or not an account at all; callers must not tell the two apart.
        """
        accounts = repository.list_member_accounts(self._session, workspace_id, user_ids)
        return MappingProxyType({account.id: account for account in accounts})

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
