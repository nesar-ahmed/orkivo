"""Domain/application exceptions for the workspaces module."""

import uuid


class WorkspaceNotFoundError(Exception):
    """The tenant does not exist, or the caller may not learn that it does.

    A non-member gets exactly this for a tenant they cannot see: revealing
    "it exists but you are not in it" would turn the directory into an oracle.
    """

    code = "WORKSPACE_NOT_FOUND"
    message = "The requested workspace was not found."

    def __init__(self, workspace_id: uuid.UUID) -> None:
        super().__init__(f"Workspace {workspace_id} was not found.")
        self.workspace_id = workspace_id


class WorkspaceSlugInUseError(Exception):
    """Another tenant already holds this slug, or it belongs to the platform."""

    code = "WORKSPACE_SLUG_IN_USE"
    message = "That workspace address is already taken."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)


class AlreadyInvitedError(Exception):
    """The address already has an open invitation to this tenant."""

    code = "INVITE_ALREADY_PENDING"
    message = "That address has already been invited."


class AlreadyMemberError(Exception):
    """The account already belongs to this tenant."""

    code = "WORKSPACE_ALREADY_MEMBER"
    message = "This account is already a member of the workspace."


class WorkspaceRoleNotAllowedError(Exception):
    """The caller's role in this tenant does not cover the operation."""

    code = "WORKSPACE_FORBIDDEN"
    message = "Your role in this workspace does not allow this action."


class LastOwnerError(Exception):
    """A tenant must always keep one owner.

    Otherwise the company is left with nobody able to change roles, and only a
    platform operator could untangle it.
    """

    code = "WORKSPACE_LAST_OWNER"
    message = "A workspace must keep at least one owner."


class InviteNotPendingError(Exception):
    """The invitation was revoked, declined, or already claimed."""

    code = "INVITE_NOT_PENDING"
    message = "This invitation is no longer available."


class WorkspaceSuspendedError(Exception):
    """A suspended tenant grants no new access until an operator restores it."""

    code = "WORKSPACE_SUSPENDED"
    message = "This workspace is suspended. Contact a workspace owner or an operator."


class PersonalWorkspaceError(Exception):
    """An operation that only makes sense for a shared tenant."""

    code = "PERSONAL_WORKSPACE_READONLY"
    message = "A personal workspace does not support this action."
