"""Comments module: the conversation on a task.

Owns: comments --- writing, editing and deleting them. Does not own: the task a
comment lives on (``tasks``, whose access rule every comment inherits through
``TaskService.authorized_task``), or the record of what happened (``activity``,
which every comment change writes to in the same transaction) (architecture doc
section 5).

A comment never changes its task's ``version``: talking about a task is not
editing it, so a colleague's comment can never make your save conflict.
"""
