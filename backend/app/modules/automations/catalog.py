"""What each automation rule does: the one place a rule is defined.

A table rather than branches in the runner, like ``workspaces.access``: adding a
rule is a new ``AutomationRule`` value plus one line here, and the runner, the
API and the settings page pick it up from this mapping.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from app.modules.automations.enums import (
    AutomationRecipient,
    AutomationRule,
    AutomationTrigger,
)


@dataclass(frozen=True)
class RuleSpec:
    """When a rule runs, and whom it notifies."""

    trigger: AutomationTrigger
    recipient: AutomationRecipient


RULES: Mapping[AutomationRule, RuleSpec] = MappingProxyType(
    {
        AutomationRule.NOTIFY_CREATOR_ON_DONE: RuleSpec(
            trigger=AutomationTrigger.TASK_COMPLETED,
            recipient=AutomationRecipient.TASK_CREATOR,
        ),
        AutomationRule.NOTIFY_WATCHERS_ON_DONE: RuleSpec(
            trigger=AutomationTrigger.TASK_COMPLETED,
            recipient=AutomationRecipient.TASK_WATCHERS,
        ),
        AutomationRule.NOTIFY_OWNERS_ON_DONE: RuleSpec(
            trigger=AutomationTrigger.TASK_COMPLETED,
            recipient=AutomationRecipient.WORKSPACE_OWNERS,
        ),
    }
)
