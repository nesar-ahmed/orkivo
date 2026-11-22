"""Persistence model for a workspace's automation settings.

Baseline schema rules (architecture doc section 6): UUID primary keys,
timezone-aware UTC timestamps, ``created_at``/``updated_at``, explicit indexes and
database constraints for hard invariants.

One row per workspace per rule, written the first time someone switches that rule
--- a rule without a row is off. The unique constraint is what makes switching
idempotent under two people clicking at once, and its leading column serves "this
workspace's rules". Deleting the workspace deletes its settings; the person who
last switched a rule is ``SET NULL`` like every other "who did it" column.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.modules.automations.enums import AutomationRule
from app.shared.time import utc_now

if TYPE_CHECKING:
    from app.modules.users.models import User


def _stored_values(enum: type[StrEnum]) -> list[str]:
    """Store enum *values*, so renaming a member cannot silently change data."""
    return [member.value for member in enum]


class AutomationSetting(Base):
    """Whether one rule is on in one workspace, and who last switched it."""

    __tablename__ = "automation_settings"
    __table_args__ = (
        UniqueConstraint("workspace_id", "rule", name="uq_automation_settings_workspace_id_rule"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "workspaces.id",
            ondelete="CASCADE",
            name="fk_automation_settings_workspace_id_workspaces",
        ),
        nullable=False,
    )
    rule: Mapped[AutomationRule] = mapped_column(
        SqlEnum(
            AutomationRule,
            name="automation_rule",
            native_enum=False,
            validate_strings=True,
            values_callable=_stored_values,
            # Room for rules added later without widening the column.
            length=64,
        ),
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "users.id", ondelete="SET NULL", name="fk_automation_settings_updated_by_id_users"
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # Joined on every read: the settings page says who switched each rule.
    updated_by: Mapped["User | None"] = relationship(foreign_keys=[updated_by_id], lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AutomationSetting workspace={self.workspace_id} rule={self.rule.value}>"
