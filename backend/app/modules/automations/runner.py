"""What the automations module offers the tasks module: running the rules.

The ``tasks`` module owns when a task is finished; it does not own what a
workspace has asked to happen then (architecture doc section 5). This is the
automations module's public answer to "these tasks were just moved to Done", so
the tasks service never reads ``automation_settings`` itself --- the same
arrangement as ``task_dependencies.blockers``.

It runs inside the tasks service's own transaction, after the save is flushed and
before it commits, and never commits: a save refused with ``409`` runs no rule,
and a committed one is never missing what its rules send (section 6.2). Whenever
a rule tells anyone, the task's history says so (``automation.notified``), so a
person wondering "why was I told?" --- or "who was?" --- can read it on the task. Rules are
read once per workspace per save, so a bulk "mark done" of a page of tasks costs
one lookup, not one per task.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.modules.activity.enums import ActivityVerb
from app.modules.activity.recorder import ActivityRecorder
from app.modules.automations import repository
from app.modules.automations.catalog import RULES
from app.modules.automations.enums import AutomationRecipient, AutomationRule, AutomationTrigger
from app.modules.notifications.notifier import Notifier
from app.modules.tasks.models import Task
from app.modules.users.models import User
from app.modules.workspaces.enums import WorkspaceRole
from app.modules.workspaces.roster import roster

#: The rules a finished task can set off.
_ON_COMPLETION = [
    rule for rule, spec in RULES.items() if spec.trigger is AutomationTrigger.TASK_COMPLETED
]


def tasks_completed(session: Session, tasks: Sequence[Task], *, actor: User) -> None:
    """``tasks`` were just moved to Done by ``actor``: run every rule that is on.

    Each person the rules name hears once per task, whichever and however many
    rules name them, and the person who finished it hears nothing.
    """
    by_workspace: dict[uuid.UUID, list[Task]] = {}
    for task in tasks:
        by_workspace.setdefault(task.workspace_id, []).append(task)

    notifier = Notifier(session)
    recorder = ActivityRecorder(session)
    for workspace_id, finished in by_workspace.items():
        switched_on = repository.enabled_rules(session, workspace_id, _ON_COMPLETION)
        recipients = {RULES[rule].recipient for rule in switched_on}
        if not recipients:
            continue
        owners = (
            {
                account.id
                for account, role in roster(session, workspace_id)
                if role is WorkspaceRole.OWNER
            }
            if AutomationRecipient.WORKSPACE_OWNERS in recipients
            else set()
        )
        for task in finished:
            people = set(owners)
            if AutomationRecipient.TASK_CREATOR in recipients:
                people.add(task.owner_id)
            told = notifier.task_completed(
                task,
                actor=actor,
                people=people,
                include_watchers=AutomationRecipient.TASK_WATCHERS in recipients,
            )
            if told:
                recorder.record(
                    ActivityVerb.AUTOMATION_NOTIFIED,
                    workspace_id=task.workspace_id,
                    actor=actor,
                    task_id=task.id,
                    task_title=task.title,
                    task_version=task.version,
                    changes={
                        "notified": {
                            "from": None,
                            "to": [{"id": str(p.id), "name": p.display_name} for p in told],
                        },
                        "rules": {
                            "from": None,
                            # In catalogue order, so the same rules always read the same.
                            "to": [str(rule) for rule in AutomationRule if rule in switched_on],
                        },
                    },
                )
