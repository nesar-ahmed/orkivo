"""SQLAlchemy persistence model for tasks.

Baseline schema rules (architecture doc section 6): UUID primary keys,
timezone-aware UTC timestamps, ``created_at``/``updated_at``, explicit
indexes and database constraints for hard invariants.

Every task lives in exactly one tenant. ``workspace_id`` is required and is the
authorization boundary: a caller reaches a task only through membership of that
workspace, decided by ``workspaces.access.WorkspaceAccessPolicy`` (architecture
doc sections 6 and 9). A task in a *personal* workspace is therefore private to
its one member, and a task in a company is shared by all of the company's members.

``owner_id`` records who created the task and ``updated_by_id`` who last changed
it. Neither decides who may see it --- a colleague edits and deletes company tasks
they did not create. The API shows both people by name, never the raw ids.

``assignee_id`` is who is expected to do the work, and is optional. It grants
nothing either: the assignee must be a member of the task's workspace, which the
service checks on every write (a foreign key cannot express "member of *this*
tenant"), and leaving a workspace releases the person's assignments in the same
transaction (``tasks.membership``).

``project_id`` files the task under one project of the *same* workspace, or
none. The service checks the workspace on every write for the same reason as the
assignee, and deleting a project detaches its tasks in the same transaction
(``tasks.project_links``); ``SET NULL`` is only the database's safety net.

``labels`` tags the task with any number of its *own* workspace's labels, through
the ``task_labels`` link table this module owns. The service checks each label's
workspace on every write, like the project, and deleting a label takes it off
every task in the same transaction (``tasks.label_links``); ``CASCADE`` is only
the database's safety net. Labels are loaded with one extra ``IN`` query per page
(``selectin``) rather than joined, so a page of tasks is never multiplied by its
labels before ``LIMIT`` applies.

``version`` is SQLAlchemy's optimistic-locking column: every UPDATE is issued as
``... WHERE id = ? AND version = ?`` and bumps it, so two colleagues saving the
same task at once cannot both win silently (see ``TaskConflictError``).
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    Uuid,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.modules.tasks.enums import TaskPriority, TaskStatus
from app.shared.time import utc_now

if TYPE_CHECKING:
    from app.modules.labels.models import Label
    from app.modules.projects.models import Project
    from app.modules.users.models import User


#: Which labels each task carries: one row per task per label. Both sides cascade
#: --- a link means nothing once either end is gone --- and the primary key makes
#: tagging a task twice with the same label impossible. Its leading column serves
#: "this task's labels"; ``ix_task_labels_label_id`` serves the label filter, the
#: per-label counts and taking a deleted label off its tasks.
task_labels = Table(
    "task_labels",
    Base.metadata,
    Column(
        "task_id",
        Uuid,
        ForeignKey("tasks.id", ondelete="CASCADE", name="fk_task_labels_task_id_tasks"),
        nullable=False,
    ),
    Column(
        "label_id",
        Uuid,
        ForeignKey("labels.id", ondelete="CASCADE", name="fk_task_labels_label_id_labels"),
        nullable=False,
    ),
    PrimaryKeyConstraint("task_id", "label_id", name="pk_task_labels"),
    Index("ix_task_labels_label_id", "label_id"),
)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        # Title must hold a non-empty value even if application validation
        # is bypassed (invariant that must survive concurrent requests).
        CheckConstraint("length(title) > 0", name="ck_tasks_title_not_empty"),
        # The board query: one tenant's tasks, newest first. The leading column
        # also serves every plain ``workspace_id`` lookup, so no second index.
        Index("ix_tasks_workspace_id_created_at", "workspace_id", "created_at"),
        # "Assigned to me / to Ana / to nobody" inside one tenant. Also the lookup
        # that releases a departing member's assignments.
        Index("ix_tasks_workspace_id_assignee_id", "workspace_id", "assignee_id"),
        # One project's tasks, its counts, and detaching them when it is deleted.
        Index("ix_tasks_workspace_id_project_id", "workspace_id", "project_id"),
        # One tenant's calendar: the tasks due inside a window of dates.
        Index("ix_tasks_workspace_id_due_date", "workspace_id", "due_date"),
        # A person's own list across every tenant, soonest due first.
        Index("ix_tasks_assignee_id_due_date", "assignee_id", "due_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Deleting a tenant deletes its work; nothing outlives the company it was in.
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE", name="fk_tasks_workspace_id_workspaces"),
        nullable=False,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE", name="fk_tasks_owner_id_users"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        SqlEnum(
            TaskStatus,
            name="task_status",
            native_enum=False,
            validate_strings=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=TaskStatus.TODO,
        index=True,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        SqlEnum(
            TaskPriority,
            name="task_priority",
            native_enum=False,
            validate_strings=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=TaskPriority.MEDIUM,
        index=True,
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Kept when the editor's account goes away: the task is the company's.
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL", name="fk_tasks_updated_by_id_users"),
        nullable=True,
    )
    # Optional, and ``SET NULL`` like ``updated_by_id``: the work stays with the
    # company when the account goes. Membership is the service's check.
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL", name="fk_tasks_assignee_id_users"),
        nullable=True,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="SET NULL", name="fk_tasks_project_id_projects"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # Joined on every read: a task is never shown without its people, and one
    # LEFT JOIN beats a query per row on a board.
    created_by: Mapped["User | None"] = relationship(foreign_keys=[owner_id], lazy="joined")
    updated_by: Mapped["User | None"] = relationship(foreign_keys=[updated_by_id], lazy="joined")
    assignee: Mapped["User | None"] = relationship(foreign_keys=[assignee_id], lazy="joined")
    project: Mapped["Project | None"] = relationship(foreign_keys=[project_id], lazy="joined")
    # Alphabetical, like every other list of labels the API returns.
    labels: Mapped[list["Label"]] = relationship(
        secondary=task_labels, lazy="selectin", order_by="Label.name_key"
    )

    __mapper_args__ = {"version_id_col": version}

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Task id={self.id} title={self.title!r} status={self.status.value}>"
