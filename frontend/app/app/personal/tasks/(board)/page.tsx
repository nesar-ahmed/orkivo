import { TaskBoard, loadTaskView, parseTaskQuery } from "@/features/tasks";
import { readPersonalWorkspace, workspacePath } from "@/features/workspaces";
import { getServerCookieHeader } from "@/lib/api/server-cookies";

export const dynamic = "force-dynamic";

export const metadata = { title: "Private tasks" };

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

/**
 * Private tasks. Nobody else is a member of this workspace, and the backend
 * offers no way to add one, so what is written here is visible to its owner only.
 */
export default async function PersonalTasksPage({ searchParams }: PageProps) {
  const cookie = await getServerCookieHeader();
  const workspace = await readPersonalWorkspace(cookie);
  if (workspace === null) throw new Error("Your private workspace could not be found.");
  const query = parseTaskQuery(await searchParams);
  const data = await loadTaskView(workspace.id, query, workspacePath(workspace, "tasks"), cookie);

  return <TaskBoard workspace={workspace} query={query} data={data} />;
}
