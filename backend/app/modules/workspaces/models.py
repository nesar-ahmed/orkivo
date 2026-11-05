"""Persistence models for workspaces (tenants), membership and invitations.

A workspace is the tenant. Nothing may reference another tenant's data without
passing through ``workspace_id``, and membership is an explicit table rather
than a convention, which is what makes cross-tenant leakage one check instead of
a hope (architecture doc sections 6 and 9).
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.modules.workspaces.enums import (
    InviteStatus,
    WorkspaceKind,
    WorkspaceRole,
    WorkspaceStatus,
)
from app.shared.time import utc_now


def _stored_values(enum: type[StrEnum]) -> list[str]:
    """Store enum *values*, so renaming a member cannot silently change data."""
    return [member.value for member in enum]


class Workspace(Base):
    """A tenant: either one person's private space or a shared company."""

    __tablename__ = "workspaces"
    __table_args__ = (
        CheckConstraint("length(name) > 0", name="ck_workspaces_name_not_empty"),
        CheckConstraint("length(name) <= 120", name="ck_workspaces_name_not_too_long"),
        # A company is addressed by its slug; a personal space is addressed by
        # nobody else, so giving one a slug would only create collisions.
        CheckConstraint(
            "(kind = 'team' AND slug IS NOT NULL) OR (kind = 'personal' AND slug IS NULL)",
            name="ck_workspaces_slug_matches_kind",
        ),
        CheckConstraint(
            "operator_note IS NULL OR length(operator_note) <= 500",
            name="ck_workspaces_operator_note_bounded",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kind: Mapped[WorkspaceKind] = mapped_column(
        SqlEnum(
            WorkspaceKind,
            name="workspace_kind",
            native_enum=False,
            validate_strings=True,
            values_callable=_stored_values,
        ),
        nullable=False,
        default=WorkspaceKind.PERSONAL,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Unique, and NULL for personal workspaces: both SQLite and PostgreSQL treat
    # NULLs as distinct, so one plain unique index serves both kinds.
    slug: Mapped[str | None] = mapped_column(String(63), nullable=True, unique=True, index=True)
    status: Mapped[WorkspaceStatus] = mapped_column(
        SqlEnum(
            WorkspaceStatus,
            name="workspace_status",
            native_enum=False,
            validate_strings=True,
            values_callable=_stored_values,
        ),
        nullable=False,
        default=WorkspaceStatus.ACTIVE,
        index=True,
    )
    # Written only by a platform operator (for instance the reason behind a
    # suspension). Deliberately not part of a member's response contract.
    operator_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Workspace id={self.id} kind={self.kind.value} slug={self.slug}>"


class WorkspaceMember(Base):
    """Explicit membership: the only thing that grants tenant access."""

    __tablename__ = "workspace_members"
    __table_args__ = (
        # One row per account per tenant. Re-adding a removed member updates this
        # row instead of creating a second membership nobody can see.
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_workspace_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE", name="fk_workspace_members_workspace"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE", name="fk_workspace_members_user"),
        nullable=False,
        index=True,
    )
    role: Mapped[WorkspaceRole] = mapped_column(
        SqlEnum(
            WorkspaceRole,
            name="workspace_role",
            native_enum=False,
            validate_strings=True,
            values_callable=_stored_values,
        ),
        nullable=False,
        default=WorkspaceRole.MEMBER,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<WorkspaceMember workspace={self.workspace_id} role={self.role.value}>"


class WorkspaceInvite(Base):
    """An address a workspace has opened, waiting for its owner to claim it.

    There is no token here, because nothing is delivered: the invitation appears
    in the profile of whoever signs in with that address. That is the whole
    mechanism today, and it is also the row a mail transport would send later
    --- adding delivery does not change this model.

    It assumes an address is proof of identity, which is what an invite to a
    known colleague means; it is why an invitation grants ``member`` and never
    more, and why an operator can still suspend the tenant around it.
    """

    __tablename__ = "workspace_invites"
    __table_args__ = (
        CheckConstraint("length(email) > 0", name="ck_workspace_invites_email_not_empty"),
        # One live invitation per address per tenant: re-invoking reopens the row.
        UniqueConstraint("workspace_id", "email", name="uq_workspace_invites_workspace_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE", name="fk_workspace_invites_workspace"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    role: Mapped[WorkspaceRole] = mapped_column(
        SqlEnum(
            WorkspaceRole,
            name="workspace_role",
            native_enum=False,
            validate_strings=True,
            values_callable=_stored_values,
        ),
        nullable=False,
        default=WorkspaceRole.MEMBER,
    )
    status: Mapped[InviteStatus] = mapped_column(
        SqlEnum(
            InviteStatus,
            name="invite_status",
            native_enum=False,
            validate_strings=True,
            values_callable=_stored_values,
        ),
        nullable=False,
        default=InviteStatus.PENDING,
        index=True,
    )
    # Nullable and SET NULL: revoking an invite must not delete the account that
    # sent it, and the account may legitimately be removed later.
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL", name="fk_workspace_invites_inviter"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        # Never the address: private content must not reach logs.
        return f"<WorkspaceInvite workspace={self.workspace_id} status={self.status.value}>"
