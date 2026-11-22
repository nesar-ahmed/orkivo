"""Activity module: the append-only record of what happened to a workspace's work.

Owns: the activity log and its two read paths (one task's history, one
workspace's feed). Does not own: the things it describes. Tasks and comments
write their own events through ``recorder.ActivityRecorder``, *inside* the
transaction that makes the change, so the log can never claim something that was
rolled back or miss something that was committed (architecture doc sections 5
and 6.2).

Nothing here updates or deletes an event. The only way an event disappears is
with its workspace, which takes everything in the tenant with it.
"""
