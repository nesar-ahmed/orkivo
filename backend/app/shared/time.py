"""Shared time helpers."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Timezone-aware UTC now, used for Python-side timestamp defaults."""
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """Return ``value`` as a timezone-aware UTC datetime.

    SQLite has no timezone-aware storage and hands back naive values, while
    PostgreSQL returns aware ones. Every timestamp is written as UTC, so a naive
    read means UTC and is normalized here before any comparison --- otherwise
    "did this session expire" becomes an offset-naive versus offset-aware
    ``TypeError`` on the sandbox database (architecture doc section 6).
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
