"""Unit tests for the tenant access policy as data (``workspaces.access``).

The policy is a table, so it is tested as one: what every role may do in an
active company, in a suspended one and in a private workspace, and which roles
each may hand out. The expected answers are written out in full rather than
derived from ``ACCESS_RULES``, so changing a rule means changing a line here too ---
a permission never widens without a test saying so (architecture doc section 9).

The services' own tests cover the refusals callers actually meet; these pin the
decisions those refusals come from.
"""

import pytest

from app.modules.workspaces.access import (
    ACCESS_RULES,
    GRANTABLE_ROLES,
    allowed_actions,
    grantable_roles,
)
from app.modules.workspaces.enums import (
    WorkspaceAction,
    WorkspaceKind,
    WorkspaceRole,
    WorkspaceStatus,
)

pytestmark = pytest.mark.unit

OWNER, ADMIN, MANAGER, MEMBER, VIEWER = (
    WorkspaceRole.OWNER,
    WorkspaceRole.ADMIN,
    WorkspaceRole.MANAGER,
    WorkspaceRole.MEMBER,
    WorkspaceRole.VIEWER,
)

#: Everything each role may do in an active company, in the enum's order.
ACTIVE_TEAM: dict[WorkspaceRole, list[str]] = {
    OWNER: [
        "read",
        "edit_content",
        "comment",
        "manage_tasks",
        "manage_projects",
        "manage_labels",
        "manage_automations",
        "leave",
        "view_invites",
        "manage",
        "invite",
        "change_roles",
    ],
    ADMIN: [
        "read",
        "edit_content",
        "comment",
        "manage_tasks",
        "manage_projects",
        "manage_labels",
        "manage_automations",
        "leave",
        "view_invites",
        "manage",
        "invite",
        "change_roles",
    ],
    MANAGER: [
        "read",
        "edit_content",
        "comment",
        "manage_tasks",
        "manage_projects",
        "manage_labels",
        "manage_automations",
        "leave",
    ],
    MEMBER: ["read", "edit_content", "comment", "leave"],
    VIEWER: ["read", "leave"],
}


def test_every_action_has_exactly_one_rule() -> None:
    assert set(ACCESS_RULES) == set(WorkspaceAction)
    assert set(GRANTABLE_ROLES) == set(WorkspaceRole)


@pytest.mark.parametrize("role", list(WorkspaceRole))
def test_what_each_role_may_do_in_an_active_company(role: WorkspaceRole) -> None:
    actions = allowed_actions(role=role, status=WorkspaceStatus.ACTIVE, kind=WorkspaceKind.TEAM)

    assert [str(action) for action in actions] == ACTIVE_TEAM[role]


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (OWNER, ["read", "view_invites"]),
        (ADMIN, ["read", "view_invites"]),
        (MANAGER, ["read"]),
        (MEMBER, ["read"]),
        (VIEWER, ["read"]),
    ],
)
def test_a_suspended_company_is_view_mode_for_every_role(
    role: WorkspaceRole, expected: list[str]
) -> None:
    actions = allowed_actions(role=role, status=WorkspaceStatus.SUSPENDED, kind=WorkspaceKind.TEAM)

    assert [str(action) for action in actions] == expected


def test_a_private_workspace_gives_its_owner_everything_but_the_group_actions() -> None:
    actions = allowed_actions(
        role=OWNER, status=WorkspaceStatus.ACTIVE, kind=WorkspaceKind.PERSONAL
    )

    assert [str(action) for action in actions] == [
        "read",
        "edit_content",
        "comment",
        "manage_tasks",
        "manage_projects",
        "manage_labels",
        "manage",
    ]


def test_roles_never_outrank_the_ones_above_them() -> None:
    """Each role may do everything the role below it may --- no sideways grants."""
    ranked = list(WorkspaceRole)
    for higher, lower in zip(ranked, ranked[1:], strict=False):
        assert set(ACTIVE_TEAM[lower]) <= set(ACTIVE_TEAM[higher]), (higher, lower)


# --- who may hand out which role --------------------------------------------
@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (OWNER, [OWNER, ADMIN, MANAGER, MEMBER, VIEWER]),
        (ADMIN, [MANAGER, MEMBER, VIEWER]),
        (MANAGER, []),
        (MEMBER, []),
        (VIEWER, []),
    ],
)
def test_which_roles_each_role_may_grant(
    role: WorkspaceRole, expected: list[WorkspaceRole]
) -> None:
    granted = grantable_roles(role=role, status=WorkspaceStatus.ACTIVE, kind=WorkspaceKind.TEAM)

    assert granted == expected


def test_nobody_grants_a_role_they_do_not_outrank_except_an_owner() -> None:
    """Only an owner creates a peer; everyone else grants strictly below themselves."""
    ranked = list(WorkspaceRole)
    for role, granted in GRANTABLE_ROLES.items():
        if role is OWNER:
            continue
        assert all(ranked.index(other) > ranked.index(role) for other in granted), role


@pytest.mark.parametrize("role", list(WorkspaceRole))
def test_nothing_is_grantable_in_view_mode_or_a_private_workspace(role: WorkspaceRole) -> None:
    suspended = grantable_roles(
        role=role, status=WorkspaceStatus.SUSPENDED, kind=WorkspaceKind.TEAM
    )
    private = grantable_roles(role=role, status=WorkspaceStatus.ACTIVE, kind=WorkspaceKind.PERSONAL)

    assert suspended == []
    assert private == []
