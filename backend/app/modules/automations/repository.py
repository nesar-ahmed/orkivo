"""Database access for automation settings.

Queries only; whether the caller may switch a rule, and what a rule does, are
decided elsewhere (``workspaces.access`` and ``catalog``) before anything here runs
(architecture doc sections 4.1 and 6.2). Every query carries the workspace.
"""

import uuid
from collections.abc import Collection, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.automations.enums import AutomationRule
from app.modules.automations.models import AutomationSetting


def settings_of(
    session: Session, workspace_id: uuid.UUID
) -> Mapping[AutomationRule, AutomationSetting]:
    """Every rule this workspace has ever switched, by rule."""
    rows = session.scalars(
        select(AutomationSetting).where(AutomationSetting.workspace_id == workspace_id)
    ).all()
    return {row.rule: row for row in rows}


def enabled_rules(
    session: Session, workspace_id: uuid.UUID, rules: Collection[AutomationRule]
) -> set[AutomationRule]:
    """Which of ``rules`` are on in the workspace, in one query."""
    if not rules:
        return set()
    return set(
        session.scalars(
            select(AutomationSetting.rule).where(
                AutomationSetting.workspace_id == workspace_id,
                AutomationSetting.rule.in_(list(rules)),
                AutomationSetting.enabled.is_(True),
            )
        )
    )


def get_setting(
    session: Session, workspace_id: uuid.UUID, rule: AutomationRule
) -> AutomationSetting | None:
    return session.scalars(
        select(AutomationSetting).where(
            AutomationSetting.workspace_id == workspace_id, AutomationSetting.rule == rule
        )
    ).first()


def add_setting(session: Session, setting: AutomationSetting) -> None:
    session.add(setting)
    session.flush()
