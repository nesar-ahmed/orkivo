"""Unit tests for settings resolution (architecture doc sections 9 and 13).

These construct ``Settings`` directly with ``_env_file=None`` and a cleared
environment, so the assertions cannot be influenced by the developer's own
``.env`` file.
"""

import pytest
from pydantic import ValidationError

from app.core.config import MIN_SECRET_KEY_LENGTH, Settings

pytestmark = pytest.mark.unit

# Long enough to satisfy the secret policy; meaningless outside these tests.
A_SECRET = "unit-test-secret-value-that-is-long-enough-to-pass"


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate from the host environment, including the ``.env`` file."""
    for name in (
        "SECRET_KEY",
        "ENVIRONMENT",
        "COOKIE_SECURE",
        "COOKIE_DOMAIN",
        "DATABASE_URL",
        "FIRST_OPERATOR_EMAIL",
    ):
        monkeypatch.delenv(name, raising=False)


def build(**overrides: object) -> Settings:
    """Build settings from explicit values only: no env, no ``.env`` file."""
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


def test_development_generates_an_ephemeral_secret() -> None:
    settings = build(environment="development")

    assert settings.secret_key is not None
    assert len(settings.secret_key) >= MIN_SECRET_KEY_LENGTH


def test_each_generated_secret_is_different() -> None:
    """The development key is per-process, so sessions cannot outlive a restart."""
    assert (
        build(environment="development").secret_key != build(environment="development").secret_key
    )


def test_an_empty_secret_counts_as_not_configured() -> None:
    """Copying the shipped ``.env.example`` must not fail with a puzzling error."""
    settings = build(environment="development", secret_key="   ")

    assert settings.secret_key is not None
    assert settings.secret_key.strip()


def test_production_refuses_to_start_without_a_secret() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY must be set"):
        build(environment="production")


def test_a_too_short_secret_is_rejected_in_any_environment() -> None:
    with pytest.raises(ValidationError, match="at least"):
        build(environment="development", secret_key="short")

    with pytest.raises(ValidationError, match="at least"):
        build(environment="production", secret_key="short")


def test_an_explicit_secret_is_kept_as_given() -> None:
    assert build(environment="development", secret_key=A_SECRET).secret_key == A_SECRET


def test_cookies_are_insecure_only_in_the_http_sandbox() -> None:
    assert build(environment="development").use_secure_cookies is False
    assert build(environment="production", secret_key=A_SECRET).use_secure_cookies is True


def test_cookie_security_can_be_overridden_explicitly() -> None:
    """Local https testing and a locked-down dev box are both legitimate setups."""
    assert (
        build(environment="production", secret_key=A_SECRET, cookie_secure=False).use_secure_cookies
        is False
    )
    assert build(environment="development", cookie_secure=True).use_secure_cookies is True


def test_token_lifetime_bounds_are_enforced() -> None:
    with pytest.raises(ValidationError):
        build(environment="development", access_token_ttl_minutes=0)

    with pytest.raises(ValidationError):
        build(environment="development", refresh_token_ttl_days=0)


# --- first-admin bootstrap -------------------------------------------------
def test_operator_email_is_absent_by_default() -> None:
    assert build(environment="development").first_operator_email is None


def test_operator_email_is_normalized_for_matching_stored_addresses() -> None:
    settings = build(environment="development", first_operator_email="  Root@Example.com ")

    assert settings.first_operator_email == "root@example.com"


def test_a_blank_operator_email_counts_as_not_configured() -> None:
    """Copying ``.env.example`` with the line present but empty must work."""
    assert build(environment="development", first_operator_email="   ").first_operator_email is None


def test_a_malformed_operator_email_fails_at_startup() -> None:
    with pytest.raises(ValidationError):
        build(environment="development", first_operator_email="not-an-address")
