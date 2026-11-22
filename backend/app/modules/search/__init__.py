"""Search module: find a workspace, project or task by name, anywhere you may look.

Owns: the one question behind the command palette --- "what is called something
like this, in any workspace I am in?" --- and how its answers are ranked. Owns no
table. Which workspaces count is ``workspaces.access`` (``readable``); the tasks and
projects found are the tasks and projects modules' answers (``tasks.lookup``,
``projects.lookup``), asked only about those workspaces (architecture doc
section 5).
"""
