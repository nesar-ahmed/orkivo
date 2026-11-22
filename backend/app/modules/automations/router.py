"""HTTP routes for a workspace's automation rules.

Routes parse/validate input, call the application service, and serialize
output. No business rules live here (architecture doc section 4.1).

* ``GET /workspaces/{workspace_id}/automations`` --- every rule in the catalogue,
  on or off. Any member; outsiders get ``WORKSPACE_NOT_FOUND``.
* ``PATCH /workspaces/{workspace_id}/automations/{rule}`` --- switch one on or off.
  Owners, admins and managers of a company; ``403`` for anyone else, and ``409
  PERSONAL_WORKSPACE_READONLY`` in a private workspace. An unknown rule is a
  validation error.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Path

from app.modules.auth.dependencies import CurrentUser
from app.modules.automations.dependencies import AutomationServiceDep
from app.modules.automations.enums import AutomationRule
from app.modules.automations.schemas import (
    AutomationPerson,
    AutomationRuleListResponse,
    AutomationRuleRead,
    AutomationRuleUpdate,
)
from app.modules.automations.service import RuleState

router = APIRouter(tags=["automations"])

WorkspaceId = Annotated[uuid.UUID, Path(description="Workspace whose rules these are.")]
Rule = Annotated[AutomationRule, Path(description="The catalogue rule to switch.")]


def _read(state: RuleState) -> AutomationRuleRead:
    return AutomationRuleRead(
        rule=state.rule,
        trigger=state.spec.trigger,
        recipient=state.spec.recipient,
        enabled=state.enabled,
        updated_by=AutomationPerson.model_validate(state.updated_by) if state.updated_by else None,
        updated_at=state.updated_at,
    )


@router.get("/workspaces/{workspace_id}/automations", response_model=AutomationRuleListResponse)
def list_automations(
    workspace_id: WorkspaceId, user: CurrentUser, service: AutomationServiceDep
) -> AutomationRuleListResponse:
    """Every automation rule, on or off, for any member of the workspace."""
    return AutomationRuleListResponse(
        items=[_read(state) for state in service.list_rules(workspace_id, actor=user)]
    )


@router.patch("/workspaces/{workspace_id}/automations/{rule}", response_model=AutomationRuleRead)
def update_automation(
    workspace_id: WorkspaceId,
    rule: Rule,
    payload: AutomationRuleUpdate,
    user: CurrentUser,
    service: AutomationServiceDep,
) -> AutomationRuleRead:
    """Switch a rule on or off. Owners, admins and managers, while the company is active."""
    return _read(service.set_enabled(workspace_id, rule, enabled=payload.enabled, actor=user))
