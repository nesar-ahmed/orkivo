/**
 * Small rules for drawing dashboards, and where each number leads.
 *
 * Every number on a dashboard is a link to the list it counts --- "3 overdue"
 * opens those three tasks --- built with the boards' own URL builders, so a
 * dashboard link and a filter picked by hand are the same address.
 */

import {
  MY_TASKS_PATH,
  myTaskQueryHref,
  parseMyTaskQuery,
  type MyTaskQuery,
} from "@/features/my-tasks/my-task-query";
import { parseTaskQuery, taskQueryHref, type TaskQuery } from "@/features/tasks/task-query";
import { workspacePath } from "@/features/workspaces/workspace-utils";
import type { Workspace } from "@/types/workspace";

/** A whole percentage of `part` in `whole`; 0 when there is nothing to divide. */
export function percent(part: number, whole: number): number {
  return whole > 0 ? Math.round((part / whole) * 100) : 0;
}

/** A bar segment's width, as a CSS percentage of `whole`. */
export function share(part: number, whole: number): string {
  return whole > 0 ? `${(part / whole) * 100}%` : "0%";
}

/** "1 task", "3 tasks". */
export function tasksLabel(count: number): string {
  return `${count} ${count === 1 ? "task" : "tasks"}`;
}

/** The workspace's task list, narrowed by `changes`. */
export function boardHref(
  workspace: Pick<Workspace, "kind" | "slug">,
  changes: Partial<TaskQuery> = {},
): string {
  // Built from an empty URL's query, so only `changes` end up in the address.
  return taskQueryHref(workspacePath(workspace, "tasks"), parseTaskQuery({}), changes);
}

/** The person's own list, narrowed by `changes` (open work, soonest due, by default). */
export function myTasksHref(changes: Partial<MyTaskQuery> = {}): string {
  return Object.keys(changes).length > 0
    ? myTaskQueryHref(parseMyTaskQuery({}), changes)
    : MY_TASKS_PATH;
}
