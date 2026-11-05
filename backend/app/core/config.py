"""Application settings, validated at startup from environment variables.

Configuration comes from the environment (and an optional local ``.env`` file).
Missing or malformed values fail fast when ``Settings`` is constructed, in line
with architecture doc section 13.
"""

import secrets
from functools import lru_cache

from pydantic import EmailStr, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Minimum length for the token signing secret; shorter values are too weak for
# HMAC signing regardless of environment.
MIN_SECRET_KEY_LENGTH = 32


class Settings(BaseSettings):
    """Runtime configuration for the backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Orkivo API"
    environment: str = Field(default="development", repr=False)

    # SQLite is supported as a lightweight sandbox; PostgreSQL is canonical.
    database_url: str = Field(default="sqlite:///./orkivo_dev.db", repr=False)

    api_v1_prefix: str = "/api/v1"

    # Browser origins allowed to call the API directly (the Next.js app).
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # --- Authentication and sessions (architecture doc section 9) ----------
    # Signing secret for access tokens. Never committed to source control: it
    # comes from the environment. Outside the local development sandbox it is
    # mandatory; an explicitly empty value counts as "not configured".
    secret_key: str | None = Field(default=None, repr=False)

    # Access tokens are short-lived; refresh sessions are long-lived but
    # revocable and rotated on use.
    access_token_ttl_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_ttl_days: int = Field(default=30, ge=1, le=180)

    # Session cookies are host-only unless a domain is configured explicitly.
    cookie_domain: str | None = None
    # ``None`` means: Secure cookies everywhere except the local http sandbox.
    cookie_secure: bool | None = Field(default=None, repr=False)

    # Address allowed to claim the platform operator role. Registration always
    # yields an ordinary account (architecture doc section 9: never trust a
    # self-supplied role), so this is how the first operator gets created. It
    # applies only while the platform has no operator at all, which makes it a
    # bootstrap and recovery path rather than a standing way to acquire
    # privilege: clear it once the account exists. It says nothing about
    # tenancy --- company authority comes only from workspace membership.
    first_operator_email: EmailStr | None = None

    @field_validator("first_operator_email", mode="before")
    @classmethod
    def _blank_operator_email_is_unset(cls, value: object) -> object:
        """Treat an empty or whitespace value as "not configured"."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("first_operator_email")
    @classmethod
    def _normalize_operator_email(cls, value: str | None) -> str | None:
        """Stored normalized, so it matches the stored (lowercase) addresses."""
        return value.lower() if value is not None else None

    @model_validator(mode="after")
    def _resolve_secrets(self) -> "Settings":
        """Fail fast on missing secrets and fall back to an ephemeral dev key."""
        if self.secret_key is not None and not self.secret_key.strip():
            # An explicitly empty value means "not configured", so copying the
            # shipped ``.env.example`` does not fail with a confusing message.
            self.secret_key = None
        if self.secret_key is None:
            if self.is_production:
                raise ValueError(
                    "SECRET_KEY must be set in the environment outside development.",
                )
            # Ephemeral per-process key: signing material stays out of source
            # control and sessions intentionally do not survive a restart.
            self.secret_key = secrets.token_urlsafe(48)
        elif len(self.secret_key) < MIN_SECRET_KEY_LENGTH:
            raise ValueError(f"SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters.")
        return self

    @property
    def is_production(self) -> bool:
        """True when not running the local development sandbox."""
        return self.environment != "development"

    @property
    def use_secure_cookies(self) -> bool:
        """Whether session cookies carry the ``Secure`` attribute.

        Default is on everywhere except the local http sandbox: a ``Secure``
        cookie is silently never sent over plain http, which would make the
        development login look broken rather than misconfigured.
        """
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.is_production


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings singleton."""
    return Settings()
