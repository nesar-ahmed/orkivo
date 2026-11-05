"""Enumerations for the workspaces (tenant) domain.

Stored as lowercase strings and part of the public API contract. The role set is
deliberately the smallest one that makes the product work; Challenge 2 widens it
with the manager/developer/viewer split, so it is the documented extension point
rather than five roles nobody uses yet (architecture doc sections 6 and 17).
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
    """Authority inside one workspace.

    ``owner`` is the accountable head: only an owner may hand the workspace to
    another owner, change roles, or delete it. Every team keeps at least one
    owner --- the service refuses the last one leaving, which is why ownership
    cannot be lost by accident. ``admin`` manages people; ``member`` does the
    work.
    """

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


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
