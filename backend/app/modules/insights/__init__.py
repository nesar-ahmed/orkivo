"""Insights module: the numbers behind a workspace's and a person's dashboard.

Owns: how work is summarised --- status counts, what is overdue or due soon, and
how open work is spread across a company's people or a person's workspaces. Owns
no table. Counting is the tasks module's (``tasks.stats``), the roster is the
workspaces module's (``workspaces.roster``), and who may see a dashboard is
``workspaces.access``, asked on every request (architecture doc section 5).
"""
