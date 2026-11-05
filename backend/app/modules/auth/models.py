"""SQLAlchemy persistence model for refresh sessions.

``RefreshSession`` is the "``RefreshToken`` or equivalent persisted session
record" required by architecture doc section 6.1. Each row is one member of a
rotation *family*: ``family_id`` groups the tokens issued from a single login,
which makes rotation and reuse detection possible.

Only the SHA-256 digest of a refresh token is stored (architecture doc
section 9).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.shared.time import utc_now


class RefreshSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE", name="fk_sessions_users_id"),
        nullable=False,
        index=True,
    )
    # Hex digest of the opaque refresh token; unique so a token maps to exactly
    # one row even before reuse detection runs.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        # Never include the token digest: session material must not reach logs.
        return f"<RefreshSession id={self.id} user_id={self.user_id}>"
