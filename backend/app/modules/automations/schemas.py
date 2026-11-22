"""Pydantic request/response contracts for the automations module.

SQLAlchemy models are never exposed directly as API responses (architecture doc
section 4.2). People are shown by name, never by email.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.automations.enums import (
    AutomationRecipient,
    AutomationRule,
    AutomationTrigger,
)


class AutomationPerson(BaseModel):
    """Who last switched a rule: enough to recognise, never an email."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str


class AutomationRuleRead(BaseModel):
    """One catalogue rule as the workspace has it.

    ``trigger`` and ``recipient`` say what the rule does, so a client can describe
    it without a copy of the catalogue. ``updated_by`` and ``updated_at`` are
    ``null`` until someone first switches it; a rule nobody switched is off.
    """

    rule: AutomationRule
    trigger: AutomationTrigger
    recipient: AutomationRecipient
    enabled: bool
    updated_by: AutomationPerson | None
    updated_at: datetime | None


class AutomationRuleListResponse(BaseModel):
    """Every rule in the catalogue, in its order. Not paginated: it is short."""

    items: list[AutomationRuleRead]


class AutomationRuleUpdate(BaseModel):
    """Switch a rule on or off."""

    enabled: bool
