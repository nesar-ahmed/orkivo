"""Application settings, validated at startup from environment variables.

Configuration comes from the environment (and an optional local ``.env`` file).
Missing or malformed values fail fast when ``Settings`` is constructed, in line
with architecture doc section 13.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings singleton."""
    return Settings()
