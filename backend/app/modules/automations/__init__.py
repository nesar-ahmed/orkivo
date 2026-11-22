"""Automations module: a workspace's rules for what happens on its own.

Owns: which automation rules a workspace has switched on, and running them when
their trigger fires ("when a task is moved to Done, tell its creator"). Does not
own the tasks that trigger them (``tasks``, which calls ``runner`` inside its own
save), the notifications they send (``notifications.Notifier``), the people they
name (``workspaces.roster``), or who may switch them (``workspaces.access``,
``manage_automations``) --- architecture doc section 5.

The rules are a fixed catalogue (``enums.AutomationRule``), switched on per
workspace, rather than a rule builder: every rule is known, reviewed and tested,
and a new one is one enum value plus one line in ``catalog.RULES``.
"""
