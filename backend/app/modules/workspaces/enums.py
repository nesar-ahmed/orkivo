"""Enumerations for the workspaces (tenant) domain.

Stored as lowercase strings and part of the public API contract: values are
added, never renamed (architecture doc sections 6 and 17). What each role may do
is not written here but in ``access.ACCESS_RULES``; these enums only name things.
"""

from enum import StrEnum


class WorkspaceKind(StrEnum):
    """What a tenant is.

    ``personal`` is created with every account, holds that person's own work and
    has exactly one member forever. ``team`` is a company: named, slugged, and
    shared by invitation. Both are the same table with the same membership rule,
    which is what keeps cross-tenant leakage a single check instead of two.
    """

    PERSONAL = "personal"
    TEAM = "team"


class WorkspaceStatus(StrEnum):
    """Tenant lifecycle, decided by a platform operator.

    ``suspended`` stops members from using the tenant's shared resources without
    deleting anything.
    """

    ACTIVE = "active"
    SUSPENDED = "suspended"


class WorkspaceRole(StrEnum):
    """Authority inside one workspace, most authority first.

    ``owner`` is the accountable head: only an owner makes another owner or an
    admin. Every team keeps at least one owner --- the service refuses the last
    one leaving, which is why ownership cannot be lost by accident. ``admin``
    manages people. ``manager`` runs the work: every task, project and label.
    ``member`` does the work: creates tasks and changes the ones they created or
    hold. ``viewer`` reads everything and changes nothing.

    Declared in rank order, which is the order every role picker offers them in.
    ``member`` keeps its stored value from before the finer split, so existing
    memberships keep exactly the rights they had to their own work.
    """

    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    MEMBER = "member"
    VIEWER = "viewer"


class InviteStatus(StrEnum):
    """One invitation row per address per workspace, cycling through these.

    ``pending`` waits for the addressee to accept from their profile. Re-invoking
    a ``revoked`` or ``declined`` address reopens the same row, so a workspace
    cannot accumulate stale duplicates of the same invite.
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    REVOKED = "revoked"


class CandidateStanding(StrEnum):
    """Why the invite picker shows someone as not available to invite again."""

    MEMBER = "member"
    """Already in the tenant."""

    INVITED = "invited"
    """Holds an open (pending) offer to join it."""


class WorkspaceAction(StrEnum):
    """What a caller is trying to do inside one tenant.

    Part of the public API contract: each workspace response lists the actions
    its caller may perform right now, so the frontend renders the decision made
    in ``access.py`` instead of re-deriving it. The rule behind each one lives in
    ``access.ACCESS_RULES``.
    """

    READ = "read"
    """See the tenant, its people, and the work stored in it."""

    EDIT_CONTENT = "edit_content"
    """Create tasks, and change or delete one's *own*: a task the caller created
    (change, delete) or holds (change), and the blockers of a task they may change.

    Which task is one's own is the tasks module's rule (``tasks.permissions``);
    this action is the part the role decides.
    """

    COMMENT = "comment"
    """Take part in a task's conversation: comment, and edit or delete one's own
    comments."""

    MANAGE_TASKS = "manage_tasks"
    """Change or delete *any* task in the tenant, whoever created or holds it."""

    MANAGE_PROJECTS = "manage_projects"
    """Create, rename and describe projects."""

    MANAGE_LABELS = "manage_labels"
    """Create, rename and recolor labels."""

    MANAGE_AUTOMATIONS = "manage_automations"
    """Switch the workspace's automation rules on and off ("when a task is moved to
    Done, tell its creator"). Every member may see which rules are on."""

    LEAVE = "leave"
    """Give up one's own membership."""

    VIEW_INVITES = "view_invites"
    """Read the tenant's invitation history."""

    MANAGE = "manage"
    """Rename the tenant, revoke invitations, remove people, delete projects,
    labels and others' comments.

    Deleting a project or a label is here rather than under ``manage_projects``
    or ``manage_labels`` because it reorganizes everyone's work at once, even
    though no task is lost.
    """

    INVITE = "invite"
    """Open the tenant to a new address."""

    CHANGE_ROLES = "change_roles"
    """Move people between roles --- only among the roles the caller may grant
    (``access.GRANTABLE_ROLES``)."""
