"""Pydantic response contracts for the search module.

SQLAlchemy models are never exposed directly as API responses (architecture doc
section 4.2). Every hit carries its workspace's kind and address, so a client can
link to it without another request.
"""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.tasks.enums import TaskPriority, TaskStatus
from app.modules.workspaces.enums import WorkspaceKind


class SearchWorkspace(BaseModel):
    """A workspace: enough to name it and build its address."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    kind: WorkspaceKind
    slug: str | None


class SearchProjectRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class SearchProjectHit(BaseModel):
    """A project that matched, and where it lives."""

    id: UUID
    name: str
    workspace: SearchWorkspace


class SearchTaskHit(BaseModel):
    """A task that matched: enough to recognise it in a list, and where it lives."""

    id: UUID
    title: str
    status: TaskStatus
    priority: TaskPriority
    due_date: date | None
    project: SearchProjectRef | None
    workspace: SearchWorkspace


class SearchResponse(BaseModel):
    """What matched ``query``, per kind, best first. Not paginated: a palette shows
    the best few and narrows as you type."""

    query: str
    workspaces: list[SearchWorkspace]
    projects: list[SearchProjectHit]
    tasks: list[SearchTaskHit]
