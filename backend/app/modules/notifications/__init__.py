"""Notifications module: who follows a task, and what they are told.

Owns: watchers (who follows a task), notifications (the inbox), and the rules
for who hears about what. Does not own: the changes that trigger them --- tasks
and comments call ``notifier.Notifier`` *inside* their own transaction, so a
notification exists exactly when the change it announces was committed
(architecture doc sections 5 and 6.2).

Everything here is scoped to current membership. A person removed from a
workspace stops watching its tasks and loses its notifications in the same
transaction, and the inbox re-checks membership on every read, so a title from a
company someone has left never reaches them.
"""
