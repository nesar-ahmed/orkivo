/**
 * Resolve the task a task URL names, for the task pages.
 *
 * Every way of not reaching a task --- a malformed id, a task that does not
 * exist, or one in a workspace the caller is not a member of --- ends in the same
 * 404 page. The API already answers those identically, and this page does not
 * invent a difference (architecture doc 8.2, section 9).
 *
 * A task the caller *can* read, opened under another workspace's URL (an old
 * link, a hand-edited one), is redirected to its canonical address. That reveals
 * nothing: the API only returned the task because the caller is a member of the
 * workspace it is being sent to.
 */

import { cache } from "react";
import { notFound, redirect } from "next/navigation";
import { fetchTask } from "@/features/tasks";
import { fetchWorkspace, taskPath } from "@/features/workspaces";
import { ApiError } from "@/lib/api/client";
import type { Task } from "@/types/task";
import type { Workspace } from "@/types/workspace";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** One API read per request, shared by `generateMetadata` and the page. */
const readTaskOnce = cache((taskId: string, cookie?: string) => fetchTask(taskId, cookie));

export async function loadTaskIn(
  workspace: Workspace,
  rawTaskId: string,
  cookie: string | undefined,
): Promise<Task> {
  // A hand-typed address should read as "no such task", not as a 422.
  if (!UUID_PATTERN.test(rawTaskId)) notFound();

  let task: Task;
  try {
    task = await readTaskOnce(rawTaskId.toLowerCase(), cookie);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    if (error instanceof ApiError && error.status === 401) redirect("/login");
    throw error;
  }

  if (task.workspace_id !== workspace.id) {
    let home: Workspace;
    try {
      home = await fetchWorkspace(task.workspace_id, cookie);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) notFound();
      throw error;
    }
    redirect(taskPath(home, task.id));
  }
  return task;
}
