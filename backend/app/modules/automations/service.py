"""Application service for a workspace's automation settings.

Business rules live here, not in route handlers. Transaction boundaries are
committed at this use-case layer and rolled back on failure (architecture doc
section 6.2).

==============================  ========================  ============================
Use case                        Action                    Who, in an active company
==============================  ========================  ============================
See which rules are on          ``read``                  every member
Switch a rule on or off         ``manage_automations``    owners, admins and managers
==============================  ========================  ============================

Every member can see which rules are on: a rule decides who is told about their
work, which is theirs to know. A suspended company's settings stay readable and
frozen, a private workspace has nothing to switch (its only person is never told
about their own action), and a workspace the caller is not in answers
``WORKSPACE_NOT_FOUND`` like everywhere else.

Rules *run* elsewhere --- ``runner``, inside the save that triggers them.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.automations import repository
from app.modules.automations.catalog import RULES, RuleSpec
from app.modules.automations.enums import AutomationRule
from app.modules.automations.models import AutomationSetting
from app.modules.users.models import User
from app.modules.workspaces.access import WorkspaceAccessPolicy
from app.modules.workspaces.enums import WorkspaceAction


@dataclass(frozen=True)
class RuleState:
    """One catalogue rule as a workspace has it: on or off, and who said so last.

    ``updated_by`` and ``updated_at`` are ``None`` for a rule nobody has switched
    yet, which is off.
    """

    rule: AutomationRule
    spec: RuleSpec
    enabled: bool
    updated_by: User | None
    updated_at: datetime | None


class AutomationService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._access = WorkspaceAccessPolicy(session)

    def list_rules(self, workspace_id: uuid.UUID, *, actor: User) -> list[RuleState]:
        """Every rule in the catalogue, in its order, as this workspace has it."""
        access = self._access.require(workspace_id, actor=actor, action=WorkspaceAction.READ)
        settings = repository.settings_of(self._session, access.workspace.id)
        return [_state(rule, settings) for rule in AutomationRule]

    def set_enabled(
        self, workspace_id: uuid.UUID, rule: AutomationRule, *, enabled: bool, actor: User
    ) -> RuleState:
        """Switch one rule on or off. Switching it to what it already is changes nothing."""
        access = self._access.require(
            workspace_id, actor=actor, action=WorkspaceAction.MANAGE_AUTOMATIONS
        )
        workspace_id = access.workspace.id
        setting = repository.get_setting(self._session, workspace_id, rule)
        if setting is None:
            setting = AutomationSetting(
                workspace_id=workspace_id, rule=rule, enabled=enabled, updated_by=actor
            )
            try:
                repository.add_setting(self._session, setting)
            except IntegrityError:
                # Someone switched it for the first time at the same instant: theirs
                # is the row now, and this switch is an ordinary change to it.
                self._session.rollback()
                setting = repository.get_setting(self._session, workspace_id, rule)
                if setting is None:  # pragma: no cover - the constraint just said it exists
                    raise
                setting.enabled = enabled
                setting.updated_by = actor
        elif setting.enabled is not enabled:
            setting.enabled = enabled
            setting.updated_by = actor
        self._commit()
        return _state(rule, {rule: setting})

    def _commit(self) -> None:
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise


def _state(rule: AutomationRule, settings: Mapping[AutomationRule, AutomationSetting]) -> RuleState:
    setting = settings.get(rule)
    return RuleState(
        rule=rule,
        spec=RULES[rule],
        enabled=setting.enabled if setting is not None else False,
        updated_by=setting.updated_by if setting is not None else None,
        updated_at=setting.updated_at if setting is not None else None,
    )
