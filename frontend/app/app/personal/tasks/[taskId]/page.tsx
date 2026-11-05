import type { Metadata } from "next";
import { TaskDetail } from "@/features/tasks";
import { hasCapability, readPersonalWorkspace, workspacePath } from "@/features/workspaces";
import { getServerCookieHeader } from "@/lib/api/server-cookies";
import type { Task } from "@/types/task";
import type { Workspace } from "@/types/workspace";
import { loadTaskIn } from "../../../_lib/load-task";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ taskId: string }>;
}

async function load(params: PageProps["params"]): Promise<{ workspace: Workspace; task: Task }> {
  const { taskId } = await params;
  const cookie = await getServerCookieHeader();
  const workspace = await readPersonalWorkspace(cookie);
  if (workspace === null) throw new Error("Your private workspace could not be found.");
  return { workspace, task: await loadTaskIn(workspace, taskId, cookie) };
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { task } = await load(params);
  return { title: `${task.title} · Private` };
}

/**
 * One private task. Only its owner is a member of this workspace, so anybody else
 * following the link gets the same 404 as for a task that does not exist.
 */
export default async function PersonalTaskPage({ params }: PageProps) {
  const { workspace, task } = await load(params);

  return (
    <TaskDetail
      key={task.id}
      task={task}
      canEdit={hasCapability(workspace, "edit_content")}
      boardPath={workspacePath(workspace, "tasks")}
      shared={false}
    />
  );
}
