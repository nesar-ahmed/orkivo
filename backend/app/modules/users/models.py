"""SQLAlchemy persistence model for users.

Baseline schema rules (architecture doc section 6): UUID primary keys,
timezone-aware UTC timestamps, ``created_at``/``updated_at``, explicit indexes
and database constraints for hard invariants.

The password hash lives on this row but is never part of an API response
(architecture doc section 7.1).
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, Text, Uuid
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.modules.users.enums import PlatformRole
from app.shared.time import utc_now


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # Email must hold a non-empty value even if application validation is
        # bypassed; uniqueness is enforced by the database, not only by code.
        CheckConstraint("length(email) > 0", name="ck_users_email_not_empty"),
        CheckConstraint("length(display_name) > 0", name="ck_users_display_name_not_empty"),
        CheckConstraint(
            "disabled_reason IS NULL OR length(disabled_reason) <= 500",
            name="ck_users_disabled_reason_bounded",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    # Argon2id encoded hash; never plaintext (architecture doc section 9).
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # The platform axis only. What an account may do inside a company comes from
    # ``workspace_members.role``, so this column can never grant tenant access
    # (architecture doc sections 5 and 9).
    platform_role: Mapped[PlatformRole] = mapped_column(
        SqlEnum(
            PlatformRole,
            name="platform_role",
            native_enum=False,
            validate_strings=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=PlatformRole.USER,
        index=True,
    )
    # Set by a platform operator to stop an account: it cannot sign in, and every
    # session it holds stops working on the next request. This is how an
    # individual is stopped --- a private workspace is never suspended. The
    # reason is for the operator record and is never shown to the account.
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disabled_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    @property
    def is_disabled(self) -> bool:
        return self.disabled_at is not None

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        # Deliberately omits email and hash: private content must not reach logs.
        return f"<User id={self.id} platform_role={self.platform_role.value}>"
