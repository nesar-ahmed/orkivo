"""Enumerations for the users domain.

Values are stored as lowercase strings and are part of the public API contract.
Do not rename existing values; document how they evolve
(architecture doc section 6).
"""

from enum import StrEnum


class PlatformRole(StrEnum):
    """Position of an account within the *platform*, not within a workspace.

    This is the only axis the ``users`` table owns. Everything a person may do
    inside a company or their own private workspace comes from
    ``workspaces.enums.WorkspaceRole`` instead, so a platform role never grants
    sight of tenant content (architecture doc sections 5 and 9).

    ``user`` is the default for every registration. ``operator`` may read the
    tenant directory and account metadata, change platform roles and suspend or
    restore a tenant; it grants no access to task, project or comment content.
    """

    USER = "user"
    OPERATOR = "operator"
