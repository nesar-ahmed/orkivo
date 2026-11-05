"""Unit tests for the auth service: rotation, reuse detection, revocation.

These exercise the rules directly, without HTTP, so a failure names the rule
rather than the transport (architecture doc sections 9 and 10.1).
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth import repository
from app.modules.auth.exceptions import InvalidCredentialsError, SessionError
from app.modules.auth.models import RefreshSession
from app.modules.auth.passwords import verify_password
from app.modules.auth.schemas import LoginRequest, RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.auth.tokens import hash_refresh_token
from app.modules.tasks.exceptions import TaskNotFoundError
from app.modules.tasks.schemas import TaskCreate
from app.modules.tasks.service import TaskService
from app.modules.users.enums import PlatformRole
from app.modules.users.exceptions import EmailAlreadyInUseError
from app.modules.users.models import User
from app.modules.workspaces.enums import WorkspaceKind, WorkspaceRole
from app.modules.workspaces.service import WorkspaceService
from tests.synth import PASSWORD, WRONG_PASSWORD, email_for

pytestmark = pytest.mark.unit


@pytest.fixture()
def service(session: Session) -> AuthService:
    return AuthService(session)


def sessions_in_order(session: Session) -> list[RefreshSession]:
    """Every stored session row, oldest first."""
    return list(
        session.scalars(
            select(RefreshSession).order_by(RefreshSession.created_at, RefreshSession.id)
        )
    )


def _register(service: AuthService, label: str) -> User:
    return service.register(RegisterRequest(email=email_for(label), password=PASSWORD))


# --- registration ----------------------------------------------------------
def test_register_stores_an_argon2_hash_for_an_ordinary_platform_role(
    service: AuthService,
) -> None:
    user = _register(service, "hashing")

    assert user.platform_role is PlatformRole.USER
    assert verify_password(PASSWORD, user.password_hash) is True
    assert verify_password(WRONG_PASSWORD, user.password_hash) is False


def test_register_creates_the_private_tenant_in_the_same_transaction(
    service: AuthService, session: Session
) -> None:
    """An account without a personal workspace would have nowhere to put work.

    Asserted through the public service rather than by poking at rows: this is the
    tenancy invariant every later query depends on, so it should survive a
    refactor of how the tenant is stored (architecture doc sections 6 and 9).
    """
    user = _register(service, "tenant")

    rows, total, _pages = WorkspaceService(session).list_for_user(user.id)
    assert total == 1
    workspace, role = rows[0]
    assert workspace.kind is WorkspaceKind.PERSONAL
    assert workspace.slug is None
    assert role is WorkspaceRole.OWNER


def test_register_normalizes_email_case(service: AuthService) -> None:
    user = service.register(RegisterRequest(email="Mixed.Case@Example.com", password=PASSWORD))

    assert user.email == "mixed.case@example.com"


def test_register_rejects_a_duplicate_email_in_any_case(service: AuthService) -> None:
    _register(service, "dupe")

    with pytest.raises(EmailAlreadyInUseError):
        service.register(RegisterRequest(email=email_for("dupe").upper(), password=PASSWORD))


def test_register_derives_a_display_name(service: AuthService) -> None:
    user = service.register(RegisterRequest(email="first.last@example.com", password=PASSWORD))

    assert user.display_name == "First Last"


# --- login -----------------------------------------------------------------
def test_login_stores_only_the_digest_of_the_refresh_token(
    service: AuthService, session: Session
) -> None:
    _register(service, "digest")

    issued = service.login(LoginRequest(email=email_for("digest"), password=PASSWORD))

    assert issued.refresh_token != hash_refresh_token(issued.refresh_token)
    assert sessions_in_order(session)[0].token_hash == hash_refresh_token(issued.refresh_token)


def test_login_rejects_a_wrong_password_and_starts_no_session(
    service: AuthService, session: Session
) -> None:
    _register(service, "guarded")

    with pytest.raises(InvalidCredentialsError):
        service.login(LoginRequest(email=email_for("guarded"), password=WRONG_PASSWORD))

    assert sessions_in_order(session) == []


def test_login_rejects_an_unknown_email_without_confirming_it(service: AuthService) -> None:
    with pytest.raises(InvalidCredentialsError) as wrong_email:
        service.login(LoginRequest(email=email_for("nobody"), password=PASSWORD))

    _register(service, "known")
    with pytest.raises(InvalidCredentialsError) as right_domain:
        service.login(LoginRequest(email=email_for("known"), password=WRONG_PASSWORD))

    # Identical failure text either way: no account enumeration.
    assert str(wrong_email.value) == str(right_domain.value)


def test_authenticate_resolves_the_session_to_its_user(service: AuthService) -> None:
    user = _register(service, "resolve")

    issued = service.login(LoginRequest(email=email_for("resolve"), password=PASSWORD))
    resolved = service.authenticate_access_token(issued.access_token)

    assert resolved.id == user.id


# --- rotation and reuse ----------------------------------------------------
def test_refresh_revokes_the_presented_session_and_keeps_the_family(
    service: AuthService, session: Session
) -> None:
    _register(service, "rotate")
    issued = service.login(LoginRequest(email=email_for("rotate"), password=PASSWORD))

    rotated = service.refresh(issued.refresh_token)

    first, second = sessions_in_order(session)
    assert first.revoked_at is not None
    assert second.revoked_at is None
    assert second.family_id == first.family_id
    assert second.token_hash == hash_refresh_token(rotated.refresh_token)
    assert rotated.refresh_token != issued.refresh_token
    assert rotated.user.id == issued.user.id


def test_replaying_a_rotated_token_revokes_the_entire_family(
    service: AuthService, session: Session
) -> None:
    _register(service, "stolen")
    stolen = service.login(LoginRequest(email=email_for("stolen"), password=PASSWORD))
    current = service.refresh(stolen.refresh_token)

    with pytest.raises(SessionError):
        service.refresh(stolen.refresh_token)

    assert all(row.revoked_at is not None for row in sessions_in_order(session))
    # The legitimate holder is logged out too: the family is treated as leaked.
    with pytest.raises(SessionError):
        service.authenticate_access_token(current.access_token)


def test_refresh_rejects_an_unknown_token(service: AuthService) -> None:
    with pytest.raises(SessionError):
        service.refresh("a-token-never-issued")


def test_logout_revokes_only_the_presented_session(service: AuthService, session: Session) -> None:
    _register(service, "devices")
    laptop = service.login(LoginRequest(email=email_for("devices"), password=PASSWORD))
    phone = service.login(LoginRequest(email=email_for("devices"), password=PASSWORD))

    service.logout(refresh_token=laptop.refresh_token, access_token=None)

    with pytest.raises(SessionError):
        service.authenticate_access_token(laptop.access_token)
    assert service.authenticate_access_token(phone.access_token).email == email_for("devices")


def test_logout_with_nothing_to_revoke_is_a_no_op(service: AuthService, session: Session) -> None:
    service.logout(refresh_token="not-a-session", access_token="not-a-token")

    assert sessions_in_order(session) == []


def test_deleting_an_account_removes_its_sessions_by_cascade(
    service: AuthService, session: Session
) -> None:
    """Referential integrity is enforced by the database, not by convention."""
    user = _register(service, "deleted")
    issued = service.login(LoginRequest(email=email_for("deleted"), password=PASSWORD))

    session.delete(user)
    session.commit()

    with pytest.raises(SessionError):
        service.authenticate_access_token(issued.access_token)
    assert sessions_in_order(session) == []


def test_deleting_an_account_removes_its_tasks_by_cascade(
    service: AuthService, session: Session
) -> None:

    user = _register(service, "task-holder")
    task = TaskService(session).create_task(TaskCreate(title="Ours"), owner_id=user.id)

    session.delete(user)
    session.commit()

    with pytest.raises(TaskNotFoundError):
        TaskService(session).get_task(task.id, owner_id=user.id)


def test_repository_helpers_find_a_session_by_id(service: AuthService, session: Session) -> None:
    _register(service, "lookup")
    issued = service.login(LoginRequest(email=email_for("lookup"), password=PASSWORD))

    record = repository.get_by_id(session, issued.session_id)

    assert record is not None
    assert record.user_id == issued.user.id
    assert repository.get_by_token_hash(session, "0" * 64) is None
