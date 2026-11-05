"""Unit tests for the first-operator bootstrap (architecture doc section 9).

Registration always yields an ordinary account and no request body may name a
role, so ``FIRST_OPERATOR_EMAIL`` is the only route to the first operator. These
tests pin the one-shot guard, and --- now that tenancy exists --- that the grant
is a *platform* role and never a membership in anyone's workspace.
"""

import pytest
from sqlalchemy.orm import Session

from app.modules.auth import service as auth_service_module
from app.modules.auth.exceptions import InvalidCredentialsError
from app.modules.auth.passwords import hash_password
from app.modules.auth.schemas import LoginRequest, RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.users.enums import PlatformRole
from app.modules.users.models import User
from app.modules.users.service import UserService
from app.modules.workspaces.enums import WorkspaceKind, WorkspaceRole
from app.modules.workspaces.service import WorkspaceService
from tests.synth import PASSWORD, WRONG_PASSWORD, email_for

pytestmark = pytest.mark.unit

BOOTSTRAP = "root@example.com"


@pytest.fixture()
def users(session: Session) -> UserService:
    return UserService(session)


@pytest.fixture()
def auth(session: Session) -> AuthService:
    return AuthService(session)


def make_account(users: UserService, address: str) -> User:
    """A registered account, exactly as registration leaves it."""
    return users.create_user(
        email=address,
        display_name="Synthetic",
        password_hash=hash_password(PASSWORD),
    )


def use_bootstrap_email(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    """Point the auth service's settings lookup at one bootstrap address."""

    class _Settings:
        first_operator_email = value

    monkeypatch.setattr(auth_service_module, "get_settings", lambda: _Settings())


# --- the grant rule --------------------------------------------------------
def test_bootstrap_promotes_the_matching_account(users: UserService) -> None:
    account = make_account(users, BOOTSTRAP)

    assert users.promote_bootstrap_operator(account, bootstrap_email=BOOTSTRAP) is True
    assert account.platform_role is PlatformRole.OPERATOR


def test_bootstrap_leaves_every_other_account_alone(users: UserService) -> None:
    account = make_account(users, email_for("someone"))

    assert users.promote_bootstrap_operator(account, bootstrap_email=BOOTSTRAP) is False
    assert account.platform_role is PlatformRole.USER


def test_bootstrap_grants_nothing_when_unset(users: UserService) -> None:
    account = make_account(users, BOOTSTRAP)

    assert users.promote_bootstrap_operator(account, bootstrap_email=None) is False
    assert account.platform_role is PlatformRole.USER


def test_bootstrap_address_comparison_ignores_case(users: UserService) -> None:
    account = make_account(users, BOOTSTRAP)

    assert users.promote_bootstrap_operator(account, bootstrap_email="ROOT@Example.com") is True
    assert account.platform_role is PlatformRole.OPERATOR


def test_bootstrap_never_grants_beside_an_existing_operator(users: UserService) -> None:
    """The one-shot guard: a repointed setting cannot produce a second operator.

    This is the shape a forgotten ``FIRST_OPERATOR_EMAIL`` takes once the first
    operator is in place.
    """
    first = make_account(users, BOOTSTRAP)
    assert users.promote_bootstrap_operator(first, bootstrap_email=BOOTSTRAP) is True

    second = make_account(users, email_for("second"))
    assert users.promote_bootstrap_operator(second, bootstrap_email=email_for("second")) is False
    assert second.platform_role is PlatformRole.USER


def test_bootstrap_does_not_touch_an_account_that_is_already_operator(
    users: UserService,
) -> None:
    account = make_account(users, BOOTSTRAP)
    account.platform_role = PlatformRole.OPERATOR

    assert users.promote_bootstrap_operator(account, bootstrap_email=BOOTSTRAP) is False


def test_promotion_grants_no_access_to_another_account_tenant(
    auth: AuthService, users: UserService, session: Session
) -> None:
    """A platform role must not smuggle tenancy along with it.

    The operator axis decides who runs the platform; only ``workspace_members``
    decides who may read a company (architecture doc section 5).
    """
    workspaces = WorkspaceService(session)
    owner = auth.register(RegisterRequest(email=email_for("company-owner"), password=PASSWORD))
    boss = auth.register(RegisterRequest(email=BOOTSTRAP, password=PASSWORD))

    owner_rows, owner_total, _owner_pages = workspaces.list_for_user(owner.id)
    owner_tenant = owner_rows[0][0]
    assert owner_total == 1

    assert users.promote_bootstrap_operator(boss, bootstrap_email=BOOTSTRAP) is True

    rows, total, _pages = workspaces.list_for_user(boss.id)
    assert total == 1
    assert rows[0][0].kind is WorkspaceKind.PERSONAL
    assert rows[0][1] is WorkspaceRole.OWNER
    assert workspaces.member_role(owner_tenant.id, boss.id) is None


# --- the sign-in path ------------------------------------------------------
def test_first_sign_in_makes_the_configured_account_an_operator(
    auth: AuthService, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_bootstrap_email(monkeypatch, BOOTSTRAP)
    auth.register(RegisterRequest(email=BOOTSTRAP, password=PASSWORD))

    issued = auth.login(LoginRequest(email=BOOTSTRAP, password=PASSWORD))

    assert issued.user.platform_role is PlatformRole.OPERATOR


def test_sign_in_grants_no_operator_role_once_one_exists(
    auth: AuthService,
    users: UserService,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_bootstrap_email(monkeypatch, email_for("late"))
    auth.register(RegisterRequest(email=email_for("late"), password=PASSWORD))
    # Committed, because the guard asks the database who the operators are.
    make_account(users, email_for("existing-operator")).platform_role = PlatformRole.OPERATOR
    session.commit()

    issued = auth.login(LoginRequest(email=email_for("late"), password=PASSWORD))

    assert issued.user.platform_role is PlatformRole.USER


def test_wrong_credentials_never_reach_the_bootstrap(
    auth: AuthService, users: UserService, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_bootstrap_email(monkeypatch, BOOTSTRAP)
    auth.register(RegisterRequest(email=BOOTSTRAP, password=PASSWORD))

    with pytest.raises(InvalidCredentialsError):
        auth.login(LoginRequest(email=BOOTSTRAP, password=WRONG_PASSWORD))

    assert users.get_user_by_email(BOOTSTRAP).platform_role is PlatformRole.USER
