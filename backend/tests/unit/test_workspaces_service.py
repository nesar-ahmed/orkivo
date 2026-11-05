"""Unit tests for workspace tenancy: membership, roles and invitations.

These exercise the rules without HTTP, so a failure names the rule rather than
the transport. The module exists for one sentence --- *access comes from a
membership row* --- and each test below is a way that could break
(architecture doc sections 5, 6 and 9).
"""

import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.workspaces.enums import InviteStatus, WorkspaceKind, WorkspaceRole
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
from app.modules.workspaces.schemas import InviteCreate, WorkspaceCreate, WorkspaceUpdate
from app.modules.workspaces.service import WorkspaceService
from tests.synth import PASSWORD, email_for, slug_for

pytestmark = pytest.mark.unit


@pytest.fixture()
def workspaces(session: Session) -> WorkspaceService:
    return WorkspaceService(session)


@pytest.fixture()
def accounts(session: Session) -> AuthService:
    return AuthService(session)


def register(accounts: AuthService, label: str):
    """A registered account, with its private tenant already created."""
    return accounts.register(RegisterRequest(email=email_for(label), password=PASSWORD))


def join(workspaces: WorkspaceService, team, actor, owner, role=WorkspaceRole.MEMBER):
    """Put an account in the tenant the way the product does: invite, then accept.

    There is no "insert membership" shortcut in the service, so a fixture that
    skipped this would be testing a state no caller can reach.
    """
    invite = workspaces.invite(team.id, InviteCreate(email=actor.email, role=role), actor=owner)
    return workspaces.accept_invitation(invite.id, actor=actor)


class Cast:
    """An owner, an admin and a member, all in one team they did not create."""

    def __init__(self, accounts: AuthService, workspaces: WorkspaceService) -> None:
        self.owner = register(accounts, "owner")
        self.admin = register(accounts, "admin")
        self.member = register(accounts, "member")
        self.team = workspaces.create_team(
            WorkspaceCreate(name="Synthetic Co", slug=slug_for("cast")), actor=self.owner
        )
        join(workspaces, self.team, self.admin, self.owner, WorkspaceRole.ADMIN)
        join(workspaces, self.team, self.member, self.owner)


@pytest.fixture()
def cast(accounts: AuthService, workspaces: WorkspaceService) -> Cast:
    return Cast(accounts, workspaces)


# --- creating a tenant -----------------------------------------------------
def test_creating_a_team_makes_the_creator_its_owner(
    cast: Cast, workspaces: WorkspaceService
) -> None:
    assert cast.team.kind is WorkspaceKind.TEAM
    assert cast.team.slug == slug_for("cast")
    assert workspaces.member_role(cast.team.id, cast.owner.id) is WorkspaceRole.OWNER


def test_registering_creates_exactly_one_personal_tenant(
    accounts: AuthService, workspaces: WorkspaceService
) -> None:
    person = register(accounts, "solo")

    rows, total, _pages = workspaces.list_for_user(person.id)

    assert total == 1
    assert rows[0][0].kind is WorkspaceKind.PERSONAL
    assert rows[0][1] is WorkspaceRole.OWNER
    # A personal tenant has no address: nothing is addressed by it.
    assert rows[0][0].slug is None


@pytest.mark.parametrize("slug", ["admin", "platform", "api", "login"])
def test_reserved_slugs_are_refused(cast: Cast, workspaces: WorkspaceService, slug: str) -> None:
    with pytest.raises(WorkspaceSlugInUseError):
        workspaces.create_team(WorkspaceCreate(name="Squatting", slug=slug), actor=cast.admin)


def test_duplicate_slug_is_refused(cast: Cast, workspaces: WorkspaceService) -> None:
    with pytest.raises(WorkspaceSlugInUseError):
        workspaces.create_team(
            WorkspaceCreate(name="Copycat", slug=slug_for("cast")), actor=cast.admin
        )


# --- reading as a member or a stranger -------------------------------------
def test_a_non_member_cannot_read_the_tenant(
    cast: Cast, workspaces: WorkspaceService, accounts: AuthService
) -> None:
    stranger = register(accounts, "stranger")

    with pytest.raises(WorkspaceNotFoundError):
        workspaces.get_readable(cast.team.id, actor=stranger)


def test_not_found_and_not_a_member_answer_identically(
    cast: Cast, workspaces: WorkspaceService, accounts: AuthService
) -> None:
    """Confirming a tenant exists is itself a leak, so the shapes must match."""
    stranger = register(accounts, "nosey")

    with pytest.raises(WorkspaceNotFoundError) as missing:
        workspaces.get_readable(uuid.uuid4(), actor=stranger)
    with pytest.raises(WorkspaceNotFoundError) as refused:
        workspaces.get_readable(cast.team.id, actor=stranger)

    assert missing.value.code == refused.value.code == "WORKSPACE_NOT_FOUND"
    assert str(missing.value) != str(refused.value)  # only the id differs


def test_any_member_may_read_the_people_list(cast: Cast, workspaces: WorkspaceService) -> None:
    rows, total, _pages = workspaces.list_members(cast.team.id, actor=cast.member)

    assert total == 3
    assert {account.id for _member, account in rows} == {
        cast.owner.id,
        cast.admin.id,
        cast.member.id,
    }


# --- role gates ------------------------------------------------------------
@pytest.mark.parametrize("role", [WorkspaceRole.MEMBER, WorkspaceRole.ADMIN])
def test_only_an_owner_changes_roles(cast: Cast, workspaces: WorkspaceService, role) -> None:
    with pytest.raises(WorkspaceRoleNotAllowedError):
        workspaces.change_member_role(cast.team.id, cast.member.id, role=role, actor=cast.admin)


def test_rename_is_allowed_for_admin_and_refused_for_member(
    cast: Cast, workspaces: WorkspaceService
) -> None:
    renamed = workspaces.rename(cast.team.id, WorkspaceUpdate(name="Renamed Co"), actor=cast.admin)

    assert renamed.name == "Renamed Co"

    with pytest.raises(WorkspaceRoleNotAllowedError):
        workspaces.rename(cast.team.id, WorkspaceUpdate(name="Nope"), actor=cast.member)


def test_an_admin_may_not_remove_the_owner(cast: Cast, workspaces: WorkspaceService) -> None:
    with pytest.raises(WorkspaceRoleNotAllowedError):
        workspaces.remove_member(cast.team.id, cast.owner.id, actor=cast.admin)

    assert workspaces.member_role(cast.team.id, cast.owner.id) is WorkspaceRole.OWNER


def test_an_admin_may_remove_a_plain_member(cast: Cast, workspaces: WorkspaceService) -> None:
    workspaces.remove_member(cast.team.id, cast.member.id, actor=cast.admin)

    assert workspaces.member_role(cast.team.id, cast.member.id) is None


def test_a_member_may_leave_but_the_last_owner_may_not(
    cast: Cast, workspaces: WorkspaceService
) -> None:
    workspaces.remove_member(cast.team.id, cast.member.id, actor=cast.member)

    with pytest.raises(LastOwnerError):
        workspaces.remove_member(cast.team.id, cast.owner.id, actor=cast.owner)


def test_the_last_owner_cannot_be_demoted(cast: Cast, workspaces: WorkspaceService) -> None:
    with pytest.raises(LastOwnerError):
        workspaces.change_member_role(
            cast.team.id, cast.owner.id, role=WorkspaceRole.MEMBER, actor=cast.owner
        )


def test_a_second_owner_unblocks_the_first(cast: Cast, workspaces: WorkspaceService) -> None:
    """Ownership is never a single point of failure once it is shared."""
    workspaces.change_member_role(
        cast.team.id, cast.admin.id, role=WorkspaceRole.OWNER, actor=cast.owner
    )

    workspaces.change_member_role(
        cast.team.id, cast.owner.id, role=WorkspaceRole.ADMIN, actor=cast.admin
    )

    assert workspaces.member_role(cast.team.id, cast.owner.id) is WorkspaceRole.ADMIN


# --- invitations -----------------------------------------------------------
def test_an_invitation_is_addressed_not_delivered(cast: Cast, workspaces: WorkspaceService) -> None:
    invite = workspaces.invite(
        cast.team.id, InviteCreate(email=email_for("newperson")), actor=cast.owner
    )

    assert invite.status is InviteStatus.PENDING
    assert invite.email == email_for("newperson")
    # Nobody joined: an invitation is an offer, not access.
    assert workspaces.count_members(cast.team.id) == 3


def test_the_addressee_sees_it_and_joins_at_the_offered_role(
    cast: Cast, workspaces: WorkspaceService, accounts: AuthService
) -> None:
    invite = workspaces.invite(
        cast.team.id,
        InviteCreate(email=email_for("joiner"), role=WorkspaceRole.ADMIN),
        actor=cast.owner,
    )
    joiner = register(accounts, "joiner")

    mine = workspaces.list_my_invitations(actor=joiner)
    assert [record.id for record, _team, _inviter in mine] == [invite.id]

    joined = workspaces.accept_invitation(invite.id, actor=joiner)

    assert joined.id == cast.team.id
    assert workspaces.member_role(cast.team.id, joiner.id) is WorkspaceRole.ADMIN


def test_only_the_invited_address_may_claim_it(cast: Cast, workspaces: WorkspaceService) -> None:
    invite = workspaces.invite(
        cast.team.id, InviteCreate(email=email_for("right")), actor=cast.owner
    )

    with pytest.raises(InviteNotPendingError):
        workspaces.accept_invitation(invite.id, actor=cast.member)

    assert workspaces.count_members(cast.team.id) == 3


def test_declining_then_being_invited_again_reopens_the_same_row(
    cast: Cast, workspaces: WorkspaceService, accounts: AuthService
) -> None:
    invite = workspaces.invite(
        cast.team.id, InviteCreate(email=email_for("fickle")), actor=cast.owner
    )
    fickle = register(accounts, "fickle")
    workspaces.decline_invitation(invite.id, actor=fickle)

    again = workspaces.invite(
        cast.team.id, InviteCreate(email=email_for("fickle")), actor=cast.owner
    )

    assert again.id == invite.id
    assert again.status is InviteStatus.PENDING


def test_a_pending_address_cannot_be_invited_twice(
    cast: Cast, workspaces: WorkspaceService
) -> None:
    workspaces.invite(cast.team.id, InviteCreate(email=email_for("once")), actor=cast.owner)

    with pytest.raises(AlreadyInvitedError):
        workspaces.invite(cast.team.id, InviteCreate(email=email_for("once")), actor=cast.owner)


def test_an_existing_member_is_not_invited(cast: Cast, workspaces: WorkspaceService) -> None:
    with pytest.raises(AlreadyMemberError):
        workspaces.invite(cast.team.id, InviteCreate(email=cast.member.email), actor=cast.owner)


def test_a_revoked_invitation_grants_nothing(
    cast: Cast, workspaces: WorkspaceService, accounts: AuthService
) -> None:
    invite = workspaces.invite(
        cast.team.id, InviteCreate(email=email_for("revoked")), actor=cast.owner
    )
    target = register(accounts, "revoked")

    workspaces.revoke_invite(cast.team.id, invite.id, actor=cast.admin)

    with pytest.raises(InviteNotPendingError):
        workspaces.accept_invitation(invite.id, actor=target)


def test_an_invitation_can_never_offer_ownership() -> None:
    """Refused by the contract itself, so no service path has to remember it."""
    with pytest.raises(ValidationError):
        InviteCreate(email=email_for("ambitious"), role=WorkspaceRole.OWNER)


def test_a_personal_tenant_takes_no_invitations(
    accounts: AuthService, workspaces: WorkspaceService
) -> None:
    person = register(accounts, "alone")
    own_rows, _own_total, _own_pages = workspaces.list_for_user(person.id)
    own_team = own_rows[0][0]

    with pytest.raises(PersonalWorkspaceError):
        workspaces.invite(own_team.id, InviteCreate(email=email_for("other")), actor=person)


def test_a_suspended_tenant_admits_nobody(
    cast: Cast, workspaces: WorkspaceService, accounts: AuthService
) -> None:
    invite = workspaces.invite(
        cast.team.id, InviteCreate(email=email_for("later")), actor=cast.owner
    )
    joiner = register(accounts, "later")

    workspaces.set_suspended(cast.team.id, suspended=True, note="test")
    with pytest.raises(WorkspaceSuspendedError):
        workspaces.accept_invitation(invite.id, actor=joiner)

    workspaces.set_suspended(cast.team.id, suspended=False, note=None)
    assert workspaces.accept_invitation(invite.id, actor=joiner).id == cast.team.id


def test_a_suspended_tenant_still_refuses_new_invitations(
    cast: Cast, workspaces: WorkspaceService
) -> None:
    workspaces.set_suspended(cast.team.id, suspended=True, note="billing")

    with pytest.raises(WorkspaceSuspendedError):
        workspaces.invite(cast.team.id, InviteCreate(email=email_for("nobody")), actor=cast.owner)
